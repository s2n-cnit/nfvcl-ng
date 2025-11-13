from typing import List, Optional, Set

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel


class GrafanaFolderModel(NFVCLBaseModel):
    uid: Optional[str] = Field(default=None)
    blueprint_id: Optional[str] = Field(default=None, description="The ID of the blueprint this folder belongs to")
    name: Optional[str] = Field(default="NFVCL")
    folders: Optional[List['GrafanaFolderModel']] = Field(default_factory=list)
    dashboards: Optional[List['GrafanaDashboardModel']] = Field(default_factory=list)

    def add_folder(self, folder: 'GrafanaFolderModel') -> None:
        """
        Add a folder to this folder's subfolders.

        Args:
            folder: The GrafanaFolderModel to add as a subfolder
        """
        if self.folders is None:
            self.folders = []
        self.folders.append(folder)

    def remove_folder(self, folder_uid: str) -> bool:
        """
        Remove a folder by its UID from this folder's subfolders.

        Args:
            folder_uid: The UID of the folder to remove

        Returns:
            bool: True if folder was found and removed, False otherwise
        """
        if self.folders is None:
            return False

        for i, folder in enumerate(self.folders):
            if folder.uid == folder_uid:
                self.folders.pop(i)
                return True
        return False

    def find_folder_by_uid(self, uid: str) -> Optional['GrafanaFolderModel']:
        """
        Recursively find a folder by its UID in this folder and all subfolders.

        Args:
            uid: The UID of the folder to find

        Returns:
            GrafanaFolderModel if found, None otherwise
        """
        if self.uid == uid:
            return self

        if self.folders:
            for folder in self.folders:
                result = folder.find_folder_by_uid(uid)
                if result:
                    return result

        return None

    def find_folder_by_blueprint_id(self, blueprint_id: str) -> Optional['GrafanaFolderModel']:
        """
        Recursively find a folder by its blueprint ID in this folder and all subfolders.

        Args:
            blueprint_id: The blueprint ID of the folder to find

        Returns:
            GrafanaFolderModel if found, None otherwise
        """
        if self.blueprint_id == blueprint_id:
            return self

        if self.folders:
            for folder in self.folders:
                result = folder.find_folder_by_blueprint_id(blueprint_id)
                if result:
                    return result

        return None

class GrafanaDashboardModel(NFVCLBaseModel):
    uid: str = Field()
    name: str = Field()


class GrafanaServerModel(NFVCLBaseModel):
    """
    Models a Grafana server instance to be managed.
    """
    id: str
    ip: str = Field(default='127.0.0.1')
    port: str = Field(default='3000')
    user: str = Field(default='ubuntu')
    password: str = Field(default='ubuntu')
    root_folder: Optional[GrafanaFolderModel] = Field(default_factory=GrafanaFolderModel)

    def folder_tree(self) -> Set[str]:
        """
        Returns a set of all folder UIDs in the Grafana server's folder structure.
        This is useful for quickly checking which folders exist without traversing the entire structure.

        Returns:
            set: A set of folder UIDs
        """
        folder_uids = set()

        def traverse_folder(folder: GrafanaFolderModel):
            if folder.uid:
                folder_uids.add(folder.uid)
            for subfolder in folder.folders or []:
                traverse_folder(subfolder)

        if self.root_folder:
            traverse_folder(self.root_folder)

        return folder_uids

    def __eq__(self, other):
        """
        Overrides the default equals implementation.
        In this way, it is possible to directly compare objects
        of this type on a given criteria (in this case the id)
        """
        if isinstance(other, GrafanaServerModel):
            return self.id == other.id
        return False

    def add_dashboard(self, dashboard: GrafanaDashboardModel, parent_folder_uid: Optional[str] = None) -> bool:
        """
        Add a dashboard to a specific folder. If no parent folder UID is provided,
        adds to the root folder.

        Args:
            dashboard: The GrafanaDashboardModel to add
            parent_folder_uid: The UID of the parent folder. If None, uses root folder.

        Returns:
            bool: True if dashboard was added successfully, False if parent folder not found
        """
        if parent_folder_uid is None:
            # Add to root folder
            self.root_folder.dashboards.append(dashboard)
            return True

        # Find the parent folder
        if self.root_folder:
            parent_folder = self.root_folder.find_folder_by_uid(parent_folder_uid)
            if parent_folder:
                if parent_folder.dashboards is None:
                    parent_folder.dashboards = []
                parent_folder.dashboards.append(dashboard)
                return True

        return False

    def remove_dashboard(self, dashboard_uid: str) -> bool:
        """
        Remove a dashboard by its UID from any folder in the server.

        Args:
            dashboard_uid: The UID of the dashboard to remove

        Returns:
            bool: True if dashboard was found and removed, False otherwise
        """
        def remove_from_folder(folder: GrafanaFolderModel) -> bool:
            # Check dashboards in current folder
            if folder.dashboards:
                for i, dashboard in enumerate(folder.dashboards):
                    if dashboard.uid == dashboard_uid:
                        folder.dashboards.pop(i)
                        return True

            # Check subfolders recursively
            if folder.folders:
                for subfolder in folder.folders:
                    if remove_from_folder(subfolder):
                        return True

            return False

        if self.root_folder:
            return remove_from_folder(self.root_folder)

        return False

    def add_folder(self, folder: GrafanaFolderModel, parent_folder_uid: Optional[str] = None) -> bool:
        """
        Add a folder to a specific parent folder. If no parent folder UID is provided,
        adds to the root folder.

        Args:
            folder: The GrafanaFolderModel to add
            parent_folder_uid: The UID of the parent folder. If None, uses root folder.

        Returns:
            bool: True if folder was added successfully, False if parent folder not found
        """
        if parent_folder_uid is None:
            # Add to root folder
            if self.root_folder is None:
                self.root_folder = GrafanaFolderModel()
            self.root_folder.add_folder(folder)
            return True

        # Find the parent folder
        if self.root_folder:
            parent_folder = self.root_folder.find_folder_by_uid(parent_folder_uid)
            if parent_folder:
                parent_folder.add_folder(folder)
                return True

        return False

    def remove_folder(self, folder_uid: str) -> bool:
        """
        Remove a folder by its UID from the server's folder structure.

        Args:
            folder_uid: The UID of the folder to remove

        Returns:
            bool: True if folder was found and removed, False otherwise
        """
        def remove_from_folder(folder: GrafanaFolderModel) -> bool:
            if folder.folders:
                for i, subfolder in enumerate(folder.folders):
                    if subfolder.uid == folder_uid:
                        folder.folders.pop(i)
                        return True
                    # Check recursively in subfolders
                    if remove_from_folder(subfolder):
                        return True
            return False

        if self.root_folder:
            # Check if we're trying to remove the root folder itself
            if self.root_folder.uid == folder_uid:
                self.root_folder = GrafanaFolderModel()  # Reset to new root
                return True
            return remove_from_folder(self.root_folder)

        return False
