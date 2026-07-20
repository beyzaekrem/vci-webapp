import json
from pathlib import Path

import cv2


class Board:
    def __init__(self, board_description_path: Path | str) -> None:
        # make self.object_points
        with Path(board_description_path).open() as file:
            board_description: dict = json.load(file)

        self.dict_name = board_description.get("aruco_dict", "4x4_1000")
        self.size = board_description.get("size", [29, 19])
        self.square_length = board_description.get("square_length", 0.040)
        self.marker_length = board_description.get("marker_length", 0.031)

        self.min_rows = board_description.get("min_rows", 10)
        self.min_points = board_description.get("min_points", 30)

        self.charuco_board = self.create_charuco_board()
        self.charuco_points = self.charuco_board.getChessboardCorners()

    def create_charuco_board(self) -> cv2.aruco.CharucoBoard:
        dict_id = self.dict_name if isinstance(self.dict_name, int) else getattr(cv2.aruco, f"DICT_{self.dict_name}")
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        return cv2.aruco.CharucoBoard(self.size, self.square_length, self.marker_length, aruco_dict)
