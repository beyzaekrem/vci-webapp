import json

import matplotlib.pyplot as plt
import numpy as np


def load_calibration(file_path):
    with open(file_path) as f:
        calib = json.load(f)
    return calib


def plot_calibration(camera_data):
    fig = plt.figure(figsize=(15, 15))
    ax = fig.add_subplot(projection="3d")
    ax.view_init(elev=15, azim=105, roll=0)
    positions = []
    for idx in range(len(camera_data["cameras"])):
        R_extrinsic = camera_data["cameras"][idx]["extrinsics"]["view_matrix"]
        R_extrinsic = np.array(R_extrinsic).reshape((4, 4))
        new_pos = -(
            (
                np.array(
                    [
                        [np.cos(82 * np.pi / 180), 0, -np.sin(82 * np.pi / 180)],
                        [0, 1, 0],
                        [np.sin(82 * np.pi / 180), 0, np.cos(82 * np.pi / 180)],
                    ]
                )
                @ np.array(
                    [
                        [1, 0, 0],
                        [0, np.cos(7 * np.pi / 180), -np.sin(7 * np.pi / 180)],
                        [0, np.sin(7 * np.pi / 180), np.cos(7 * np.pi / 180)],
                    ]
                )
            )
            @ np.array(R_extrinsic[:3, :3]).T
            @ R_extrinsic[:3, 3]
        )

        # new_pos = -(R_extrinsic.transpose() @ R_extrinsic[:, -1])[:-1]
        new_pos = new_pos * [1, -1, -1]
        positions.append(new_pos)

        # openvc: (left-hand, x left, z forward, y down)
        ax.set_xlabel("X (left)")  # matlab x is right
        ax.set_ylabel("Z (forward)")  # y is into scene
        ax.set_zlabel("Y (up)")  # z is up

        ax.scatter(new_pos[0], new_pos[1], new_pos[2])  #  color=color(new_pos))
        ax.text(new_pos[0], new_pos[1], new_pos[2], camera_data["cameras"][idx]["camera_id"])
    ax.scatter(0, 0, 0)
    positions = np.array(positions)
    plt.savefig("hallo.png")
    plt.show()


def color(pos):
    r = (pos[0] + 5) / 6  # [-5 , 0.1]
    g = (pos[1] + 3) / 6  # [-2.3, 2.6]
    b = (pos[2] + 2) / 4  # [-1.5, 1.3]
    print(r, g, b)
    return r, g, b


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="show camera positions")
    parser.add_argument(
        "--path",
        help="path/to/calibration_dome.json",
    )
    args = parser.parse_args()
    calib = load_calibration(args.path)
    plot_calibration(calib)
