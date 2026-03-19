"""Tree utilities for Foggy Framework."""

from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")


@dataclass
class TreeNode(Generic[T]):
    """Tree node data structure."""

    id: str
    name: str
    value: Optional[T] = None
    parent_id: Optional[str] = None
    children: List["TreeNode[T]"] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def add_child(self, child: "TreeNode[T]") -> None:
        """Add a child node."""
        child.parent_id = self.id
        self.children.append(child)

    def is_leaf(self) -> bool:
        """Check if this node is a leaf (has no children)."""
        return len(self.children) == 0

    def depth(self) -> int:
        """Get the depth of this node (root has depth 1)."""
        if self.is_leaf():
            return 1
        return 1 + max(child.depth() for child in self.children)

    def flatten(self) -> List["TreeNode[T]"]:
        """Flatten tree into a list (pre-order traversal)."""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result


class TreeUtils:
    """Tree utility functions."""

    @staticmethod
    def build_tree(
        nodes: List[Dict[str, Any]],
        id_key: str = "id",
        parent_key: str = "parentId",
        name_key: str = "name",
    ) -> List[TreeNode[Any]]:
        """Build tree structure from flat list of nodes.

        Args:
            nodes: List of node dictionaries
            id_key: Key for node ID
            parent_key: Key for parent ID
            name_key: Key for node name

        Returns:
            List of root TreeNodes
        """
        # Create all nodes
        node_map: Dict[str, TreeNode[Any]] = {}
        for node_data in nodes:
            node_id = str(node_data.get(id_key, ""))
            name = str(node_data.get(name_key, ""))
            parent_id = node_data.get(parent_key)

            node = TreeNode(
                id=node_id,
                name=name,
                parent_id=str(parent_id) if parent_id else None,
                attributes=node_data,
            )
            node_map[node_id] = node

        # Build tree structure
        roots: List[TreeNode[Any]] = []
        for node in node_map.values():
            if node.parent_id and node.parent_id in node_map:
                node_map[node.parent_id].add_child(node)
            else:
                roots.append(node)

        return roots

    @staticmethod
    def find_node(tree: List[TreeNode[Any]], node_id: str) -> Optional[TreeNode[Any]]:
        """Find a node by ID in the tree.

        Args:
            tree: List of root nodes
            node_id: ID to find

        Returns:
            TreeNode if found, None otherwise
        """
        for node in tree:
            if node.id == node_id:
                return node
            if node.children:
                result = TreeUtils.find_node(node.children, node_id)
                if result:
                    return result
        return None

    @staticmethod
    def get_all_descendants(node: TreeNode[Any]) -> List[TreeNode[Any]]:
        """Get all descendants of a node.

        Args:
            node: Parent node

        Returns:
            List of all descendant nodes
        """
        result: List[TreeNode[Any]] = []
        for child in node.children:
            result.append(child)
            result.extend(TreeUtils.get_all_descendants(child))
        return result

    @staticmethod
    def get_path_to_root(
        node: TreeNode[Any], node_map: Dict[str, TreeNode[Any]]
    ) -> List[TreeNode[Any]]:
        """Get path from node to root.

        Args:
            node: Starting node
            node_map: Map of all nodes by ID

        Returns:
            List of nodes from current to root
        """
        path = [node]
        current = node
        while current.parent_id and current.parent_id in node_map:
            current = node_map[current.parent_id]
            path.append(current)
        return path