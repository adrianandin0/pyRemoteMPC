import copy
import uuid
from typing import Optional, List
from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QInputDialog
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Signal
from pyremotempc.config.models import ConnectionNode
from pyremotempc.ui.icon_manager import get_icon, get_node_icon


class ConnectionTreeWidget(QTreeWidget):
    """
    Hierarchical Connections and Folders Tree Widget.
    Persists expand/collapse state per node ID in user settings.
    """
    node_selected = Signal(ConnectionNode)
    node_activated = Signal(ConnectionNode)  # Double click / Enter to connect
    tree_changed = Signal()

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self._settings = settings  # SettingsManager instance for persisting expand state
        self.setHeaderLabel("Connections")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Connect both selection and current item signals for instantaneous property inspector update
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.currentItemChanged.connect(self._on_current_item_changed)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

        # Save expansion state whenever a folder is expanded or collapsed
        self.itemExpanded.connect(self._on_expansion_changed)
        self.itemCollapsed.connect(self._on_expansion_changed)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)

        self.root_node: ConnectionNode = ConnectionNode(name="Connections", node_type="Container", icon="Connections")

    def filter_nodes(self, query: str):
        """Filters connection tree items in real-time based on query (name, hostname, username, description)."""
        query = query.strip().lower()

        def _filter_item_recursive(item: QTreeWidgetItem) -> bool:
            node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
            matches = False
            if node:
                name_match = query in (node.name or "").lower()
                host_match = query in (node.hostname or "").lower()
                user_match = query in (node.username or "").lower()
                desc_match = query in (node.description or "").lower()
                matches = name_match or host_match or user_match or desc_match

            any_child_matches = False
            for i in range(item.childCount()):
                child_item = item.child(i)
                if _filter_item_recursive(child_item):
                    any_child_matches = True

            visible = not query or matches or any_child_matches
            item.setHidden(not visible)

            if visible and query:
                item.setExpanded(True)

            return visible

        self.setUpdatesEnabled(False)
        for i in range(self.topLevelItemCount()):
            top_item = self.topLevelItem(i)
            _filter_item_recursive(top_item)
        self.setUpdatesEnabled(True)

    # ── Expansion state persistence ──────────────────────────────────────────

    def _on_expansion_changed(self, item=None):
        """Saves currently expanded node IDs to settings."""
        if not self._settings:
            return
        expanded_ids: List[str] = []
        self._collect_expanded_ids(self.invisibleRootItem(), expanded_ids)
        self._settings.set("tree_expanded_ids", expanded_ids)

    def _collect_expanded_ids(self, parent_item, result: List[str]):
        count = parent_item.childCount() if isinstance(parent_item, QTreeWidgetItem) else self.topLevelItemCount()
        for i in range(count):
            item = parent_item.child(i) if isinstance(parent_item, QTreeWidgetItem) else self.topLevelItem(i)
            node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
            if node and node.is_container() and item.isExpanded():
                result.append(node.id)
            self._collect_expanded_ids(item, result)

    def _restore_expansion_state(self, expanded_ids: List[str]):
        """Restores tree item expansion state from saved node IDs."""
        expanded_set = set(expanded_ids)
        self._apply_expansion_recursive(self.invisibleRootItem(), expanded_set)

    def _apply_expansion_recursive(self, parent_item, expanded_set: set):
        count = parent_item.childCount() if isinstance(parent_item, QTreeWidgetItem) else self.topLevelItemCount()
        has_root_in_set = any(k.startswith("ROOT_") for k in expanded_set)
        for i in range(count):
            item = parent_item.child(i) if isinstance(parent_item, QTreeWidgetItem) else self.topLevelItem(i)
            node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
            if node and node.is_container():
                is_root = (node == self.root_node or node.id == self.root_node.id or node.id.startswith("ROOT_") or getattr(node, "parent_id", None) is None)
                if is_root and not has_root_in_set:
                    should_expand = True
                else:
                    should_expand = node.id in expanded_set
                item.setExpanded(should_expand)
            self._apply_expansion_recursive(item, expanded_set)

    # ── Load / Populate ───────────────────────────────────────────────────

    def load_tree(self, root_node: ConnectionNode):
        """Loads a ConnectionNode tree into the widget, restoring saved expansion state."""
        if root_node and root_node.name and root_node.name.strip().lower() in ("conexiones", "connections"):
            root_node.name = "Connections"

        # Read saved expansion state BEFORE clear() triggers itemCollapsed signals!
        saved_ids = self._settings.get("tree_expanded_ids", None) if self._settings else None

        self.blockSignals(True)
        self.setUpdatesEnabled(False)
        self.clear()
        self.root_node = root_node
        self._populate_item(self.invisibleRootItem(), root_node)

        if saved_ids is None:
            self.expandAll()
        else:
            self._restore_expansion_state(saved_ids)

        self.setUpdatesEnabled(True)
        self.blockSignals(False)

        # Save expansion state if this was first run
        if saved_ids is None:
            self._on_expansion_changed()

        # Select root "Connections" node by default on startup
        if self.topLevelItemCount() > 0:
            top_item = self.topLevelItem(0)
            self.setCurrentItem(top_item)

    def _expand_recursive(self, item: QTreeWidgetItem, expand: bool = True):
        """Recursively expands or collapses an item and all its child items."""
        self.blockSignals(True)
        def _do_expand(it: QTreeWidgetItem):
            it.setExpanded(expand)
            for i in range(it.childCount()):
                _do_expand(it.child(i))
        _do_expand(item)
        self.blockSignals(False)
        self._on_expansion_changed()

    def sync_root_node_from_ui(self):
        """Rebuilds self.root_node.children structure from current visual QTreeWidget hierarchy."""
        if not hasattr(self, "root_node") or not self.root_node:
            return

        def _build_children_from_item(parent_item: QTreeWidgetItem, parent_node: ConnectionNode):
            count = parent_item.childCount()
            new_children = []
            for i in range(count):
                item = parent_item.child(i)
                node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
                if node:
                    node.parent_id = parent_node.id
                    if node.is_container():
                        _build_children_from_item(item, node)
                    new_children.append(node)
            parent_node.children = new_children

        if self.topLevelItemCount() == 1:
            top_item = self.topLevelItem(0)
            top_node: ConnectionNode = top_item.data(0, Qt.ItemDataRole.UserRole)
            if top_node and top_node.id == self.root_node.id:
                _build_children_from_item(top_item, self.root_node)
                return

        count = self.topLevelItemCount()
        new_children = []
        for i in range(count):
            item = self.topLevelItem(i)
            node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
            if node:
                node.parent_id = self.root_node.id
                if node.is_container():
                    _build_children_from_item(item, node)
                new_children.append(node)
        self.root_node.children = new_children

    def dropEvent(self, event):
        super().dropEvent(event)
        self.sync_root_node_from_ui()
        self.tree_changed.emit()

    def update_node_display(self, node: ConnectionNode):
        """Updates the tree item text and icon display for a modified node."""
        self._update_item_text_recursive(self.invisibleRootItem(), node)

    def _update_item_text_recursive(self, parent_item, target_node: ConnectionNode) -> bool:
        count = parent_item.childCount() if isinstance(parent_item, QTreeWidgetItem) else self.topLevelItemCount()
        for i in range(count):
            item = parent_item.child(i) if isinstance(parent_item, QTreeWidgetItem) else self.topLevelItem(i)
            n: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
            if n and n.id == target_node.id:
                item.setText(0, target_node.name)
                item.setIcon(0, get_node_icon(target_node))
                return True
            if self._update_item_text_recursive(item, target_node):
                return True
        return False

    def _populate_item(self, parent_item: QTreeWidgetItem, node: ConnectionNode):
        item = QTreeWidgetItem()
        item.setText(0, node.name)
        item.setData(0, Qt.ItemDataRole.UserRole, node)
        item.setIcon(0, get_node_icon(node))

        if isinstance(parent_item, QTreeWidgetItem):
            parent_item.addChild(item)
        else:
            self.addTopLevelItem(item)

        for child in node.children:
            self._populate_item(item, child)

    def _on_selection_changed(self):
        items = self.selectedItems()
        if items:
            node: ConnectionNode = items[0].data(0, Qt.ItemDataRole.UserRole)
            if node:
                self.node_selected.emit(node)

    def _on_current_item_changed(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        if current:
            node: ConnectionNode = current.data(0, Qt.ItemDataRole.UserRole)
            if node:
                self.node_selected.emit(node)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
        if node and not node.is_container():
            self.node_activated.emit(node)

    def get_selected_node(self) -> Optional[ConnectionNode]:
        items = self.selectedItems()
        if items:
            return items[0].data(0, Qt.ItemDataRole.UserRole)
        return None

    def add_new_connection(self, parent_node: Optional[ConnectionNode] = None, new_node: Optional[ConnectionNode] = None) -> ConnectionNode:
        self.sync_root_node_from_ui()
        if parent_node is None:
            parent_node = self.get_selected_node() or self.root_node

        if not parent_node.is_container():
            parent_node = self.root_node

        if new_node is None:
            new_node = ConnectionNode(
                name="New Connection",
                node_type="Connection",
                protocol="SSH2",
                port=22,
                hostname="127.0.0.1",
                parent_id=parent_node.id
            )
        else:
            new_node.parent_id = parent_node.id

        parent_node.children.append(new_node)
        self.load_tree(self.root_node)

        # Select the newly added item in tree
        self._select_node_item(self.invisibleRootItem(), new_node.id)
        self.tree_changed.emit()
        return new_node

    def _select_node_item(self, parent_item, target_id: str) -> bool:
        count = parent_item.childCount() if isinstance(parent_item, QTreeWidgetItem) else self.topLevelItemCount()
        for i in range(count):
            item = parent_item.child(i) if isinstance(parent_item, QTreeWidgetItem) else self.topLevelItem(i)
            node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
            if node and node.id == target_id:
                self.setCurrentItem(item)
                return True
            if self._select_node_item(item, target_id):
                return True
        return False

    def add_new_folder(self, parent_node: Optional[ConnectionNode] = None) -> ConnectionNode:
        self.sync_root_node_from_ui()
        if parent_node is None:
            parent_node = self.get_selected_node() or self.root_node

        if not parent_node.is_container():
            parent_node = self.root_node

        new_folder = ConnectionNode(
            name="New Folder",
            node_type="Container",
            icon="Folder",
            parent_id=parent_node.id
        )
        parent_node.children.append(new_folder)
        self.load_tree(self.root_node)
        self._select_node_item(self.invisibleRootItem(), new_folder.id)
        self.tree_changed.emit()
        return new_folder

    def rename_node(self, node: Optional[ConnectionNode] = None):
        if node is None:
            node = self.get_selected_node()
        if not node or node == self.root_node:
            return

        new_name, ok = QInputDialog.getText(
            self,
            "Rename",
            "New name:",
            text=node.name
        )
        if ok and new_name.strip():
            node.name = new_name.strip()
            self.update_node_display(node)
            self.tree_changed.emit()

    def delete_selected_node(self):
        node = self.get_selected_node()
        if not node or node == self.root_node:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{node.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._remove_node_recursive(self.root_node, node.id)
            self.load_tree(self.root_node)
            self.tree_changed.emit()

    def _remove_node_recursive(self, parent: ConnectionNode, target_id: str) -> bool:
        for child in list(parent.children):
            if child.id == target_id:
                parent.children.remove(child)
                return True
            if child.is_container():
                if self._remove_node_recursive(child, target_id):
                    return True
        return False

    def _find_parent_node_recursive(self, current: ConnectionNode, target_id: str) -> Optional[ConnectionNode]:
        for child in current.children:
            if child.id == target_id:
                return current
            if child.is_container():
                found = self._find_parent_node_recursive(child, target_id)
                if found:
                    return found
        return None

    def move_node_up(self, node: Optional[ConnectionNode] = None):
        """Moves selected node up by 1 position among its siblings."""
        if node is None:
            node = self.get_selected_node()
        if not node or node == self.root_node:
            return

        self.sync_root_node_from_ui()
        parent_node = self._find_parent_node_recursive(self.root_node, node.id)
        if not parent_node:
            return

        idx = next((i for i, c in enumerate(parent_node.children) if c.id == node.id), -1)
        if idx > 0:
            parent_node.children[idx], parent_node.children[idx - 1] = parent_node.children[idx - 1], parent_node.children[idx]
            self.load_tree(self.root_node)
            self._select_node_item(self.invisibleRootItem(), node.id)
            self.tree_changed.emit()

    def move_node_down(self, node: Optional[ConnectionNode] = None):
        """Moves selected node down by 1 position among its siblings."""
        if node is None:
            node = self.get_selected_node()
        if not node or node == self.root_node:
            return

        self.sync_root_node_from_ui()
        parent_node = self._find_parent_node_recursive(self.root_node, node.id)
        if not parent_node:
            return

        idx = next((i for i, c in enumerate(parent_node.children) if c.id == node.id), -1)
        if idx >= 0 and idx < len(parent_node.children) - 1:
            parent_node.children[idx], parent_node.children[idx + 1] = parent_node.children[idx + 1], parent_node.children[idx]
            self.load_tree(self.root_node)
            self._select_node_item(self.invisibleRootItem(), node.id)
            self.tree_changed.emit()

    def _deep_copy_node(self, node: ConnectionNode, new_parent_id: Optional[str] = None) -> ConnectionNode:
        """Deep copies a ConnectionNode with fresh UUIDs assigned recursively."""
        new_node = copy.deepcopy(node)
        new_node.id = str(uuid.uuid4())
        new_node.name = f"{node.name} (Copy)"
        new_node.parent_id = new_parent_id

        def _reassign_ids(n: ConnectionNode, p_id: str):
            for child in n.children:
                child.id = str(uuid.uuid4())
                child.parent_id = p_id
                _reassign_ids(child, child.id)

        _reassign_ids(new_node, new_node.id)
        return new_node

    def clone_node(self, node: Optional[ConnectionNode] = None) -> Optional[ConnectionNode]:
        """Clones a connection or container node and inserts it right after original."""
        if node is None:
            node = self.get_selected_node()
        if not node or node == self.root_node:
            return None

        self.sync_root_node_from_ui()
        parent_node = self._find_parent_node_recursive(self.root_node, node.id) or self.root_node

        cloned_node = self._deep_copy_node(node, parent_node.id)

        idx = next((i for i, c in enumerate(parent_node.children) if c.id == node.id), len(parent_node.children) - 1)
        parent_node.children.insert(idx + 1, cloned_node)

        self.load_tree(self.root_node)
        self._select_node_item(self.invisibleRootItem(), cloned_node.id)
        self.tree_changed.emit()
        return cloned_node

    def get_suggested_import_folder_name(self, base_name: str = "Imported from File") -> str:
        """Calculates a unique default folder name like 'Imported from File' or 'Imported from File (1)'."""
        self.sync_root_node_from_ui()
        existing_names = {child.name.strip() for child in self.root_node.children if child.name}
        if base_name not in existing_names:
            return base_name
        counter = 1
        while f"{base_name} ({counter})" in existing_names:
            counter += 1
        return f"{base_name} ({counter})"

    def import_nodes_into_new_folder(self, imported_root: ConnectionNode, folder_name: str = "Imported from File", folder_icon: str = "Folder") -> ConnectionNode:
        """Appends imported connection tree inside a new container folder with custom name and icon."""
        self.sync_root_node_from_ui()

        import_folder = ConnectionNode(
            name=folder_name,
            node_type="Container",
            icon=folder_icon,
            parent_id=self.root_node.id
        )

        children_to_add = imported_root.children if imported_root.children else [imported_root]
        for child in children_to_add:
            child.parent_id = import_folder.id
            import_folder.children.append(child)

        self.root_node.children.append(import_folder)
        self.load_tree(self.root_node)
        self._select_node_item(self.invisibleRootItem(), import_folder.id)
        self.tree_changed.emit()
        return import_folder

    def _show_context_menu(self, position):
        item = self.itemAt(position)
        menu = QMenu(self)

        if item:
            node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
            is_root = (node == self.root_node or node.id == self.root_node.id)

            if not node.is_container():
                action_connect = menu.addAction(get_icon("connect"), "Connect")
                action_connect.triggered.connect(lambda: self.node_activated.emit(node))
                menu.addSeparator()

            action_new_conn = menu.addAction(get_icon("add"), "New Connection")
            action_new_conn.triggered.connect(lambda: self.add_new_connection(node))

            action_new_folder = menu.addAction(get_icon("folder"), "New Folder")
            action_new_folder.triggered.connect(lambda: self.add_new_folder(node))

            if not is_root:
                action_clone = menu.addAction(get_icon("copy"), "Clone")
                action_clone.triggered.connect(lambda: self.clone_node(node))

                menu.addSeparator()
                action_up = menu.addAction(get_icon("upload"), "Up")
                action_up.triggered.connect(lambda: self.move_node_up(node))

                action_down = menu.addAction(get_icon("download"), "Down")
                action_down.triggered.connect(lambda: self.move_node_down(node))

            menu.addSeparator()
            action_rename = menu.addAction(get_icon("edit"), "Rename")
            action_rename.triggered.connect(lambda: self.rename_node(node))

            if node.is_container():
                action_expand_all = menu.addAction(get_icon("folder"), "Expand All")
                action_expand_all.triggered.connect(lambda: self._expand_recursive(item, True))
                action_collapse_all = menu.addAction(get_icon("folder"), "Collapse All")
                action_collapse_all.triggered.connect(lambda: self._expand_recursive(item, False))

            if not is_root:
                action_delete = menu.addAction(get_icon("trash"), "Delete")
                action_delete.triggered.connect(self.delete_selected_node)
        else:
            action_new_conn = menu.addAction(get_icon("add"), "New Connection")
            action_new_conn.triggered.connect(lambda: self.add_new_connection(self.root_node))

            action_new_folder = menu.addAction(get_icon("folder"), "New Folder")
            action_new_folder.triggered.connect(lambda: self.add_new_folder(self.root_node))

        menu.exec_(self.viewport().mapToGlobal(position))
