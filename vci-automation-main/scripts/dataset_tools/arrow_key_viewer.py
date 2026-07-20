# ruff: noqa: INP001
"""
A program that lets you see the photos taken by the Capture Stage cameras in a seemless way moving along the cylinder rather than according to frame name. Functionality:
- Button: Load images in folder
- Button: Rotate images
- Button: Save rotated images
- Up-Key: go up one level in the capture stage
- Down-Key: go down one level in the capture stage
- Left-Key: go left in the capture stage
- Right-Key: go right in the capture stage
- Top right shows current position on the capture stage setup: 12 pillars; 5 possible position; red indicates no camera available, green indicates camera available, blue indicates current position
"""

import json
import os

import customtkinter as ctk
import numpy as np
from customtkinter import CTkButton, CTkFrame, CTkLabel, filedialog
from PIL import Image

CAMERAS = [
    [
        "/C0025.jpg",
        "",
        "/C0039.jpg",
        "",
        "/C0031.jpg",
        "",
        "/C0019.jpg",
        "",
        "/C0024.jpg",
        "",
        "/C0030.jpg",
        "",
    ],
    [
        "",
        "/C0016.jpg",
        "",
        "/C0009.jpg",
        "",
        "",
        "",
        "/C0014.jpg",
        "",
        "/C0040.jpg",
        "",
        "/C0000.jpg",
    ],
    [
        "/C0038.jpg",
        "/C0007.jpg",
        "/C0018.jpg",
        "/C0004.jpg",
        "/C0034.jpg",
        "/C0006.jpg",
        "/C0008.jpg",
        "/C0026.jpg",
        "/C0005.jpg",
        "/C0028.jpg",
        "/C0029.jpg",
        "/C0012.jpg",
    ],
    [
        "/C1005.jpg",
        "",
        "/C0020.jpg",
        "",
        "/C0021.jpg",
        "",
        "/C0037.jpg",
        "",
        "/C1000.jpg",
        "",
        "/C0022.jpg",
        "",
    ],
    [
        "",
        "/C0010.jpg",
        "",
        "/C1002.jpg",
        "",
        "/C1004.jpg",
        "",
        "/C0013.jpg",
        "",
        "/C0001.jpg",
        "",
        "/C1001.jpg",
    ],
]
CAMERA_POS = (0, 11)
FOLDER = None
IMAGE = None


def load_image(path, x, y, dir=None):
    global CAMERA_POS
    global IMAGE

    if path is not None:
        try:
            img = Image.open(path)
            img = img.resize((1000, 1000), Image.LANCZOS)  # Resize image for display
            IMAGE = img
            image_label.configure(image=ctk.CTkImage(img, size=(1000, 1000)))
            CELLS[(x, y)].configure(text="active", bg_color="blue")
            if CAMERA_POS != (0, 11) and (x, y) != CAMERA_POS:
                CELLS[(CAMERA_POS[0], CAMERA_POS[1])].configure(text="", bg_color="green")
            CAMERA_POS = (x, y)
        except Exception:
            CELLS[(x, y)].configure(text="unav.", bg_color="purple", font=("Modern", 10))
            if dir == "top":
                get_above_image(x, y)
            elif dir == "bottom":
                get_below_image(x, y)
            elif dir == "left":
                get_left_image(x, y)
            elif dir == "right":
                get_right_image(x, y)


def btn1_load_directory():
    global FOLDER
    global CELLS
    FOLDER = filedialog.askdirectory(title="Choose folder containing images", initialdir="/")
    CELLS = {}
    reset_cells(CELLS)
    load_image(FOLDER + "/C0004.jpg", 2, 3)


def btn2_rotate_image():
    global IMAGE
    if IMAGE is None:
        return
    rot_img = np.asarray(IMAGE)
    rot_img = np.rot90(rot_img, -1)
    img = Image.fromarray(rot_img)
    IMAGE = img
    image_label.configure(image=ctk.CTkImage(img, size=(1000, 1000)))
    image_label.image = img


def btn3_save_rotation():
    global FOLDER
    if FOLDER is None:
        return
    try:
        os.makedirs(FOLDER + "_rotated")
    except Exception:
        return
    for file in os.listdir(FOLDER):
        img = Image.open(os.path.join(FOLDER, file))
        img = np.asarray(img)
        with open("./config.json") as f:
            data = json.load(f)
        for i in range(len(data["camera_params"])):
            if data["camera_params"][i]["id"] == file.split(".")[0]:
                if data["camera_params"][i]["extrinsics"][0] < -0.5:
                    direction = 1
                elif data["camera_params"][i]["extrinsics"][0] > 0.5:
                    direction = -1
                else:
                    direction = 0
        rot_img = np.rot90(img, direction)
        rot_img = Image.fromarray(rot_img)
        rot_img.save(FOLDER + "_rotated/" + file)
    FOLDER = FOLDER + "_rotated"

    load_image(
        FOLDER + "/" + CAMERAS[CAMERA_POS[0]][CAMERA_POS[1]],
        CAMERA_POS[0],
        CAMERA_POS[1],
    )


def above_image(event):
    get_above_image(CAMERA_POS[0], CAMERA_POS[1])


def below_image(event):
    get_below_image(CAMERA_POS[0], CAMERA_POS[1])


def left_image(event):
    get_left_image(CAMERA_POS[0], CAMERA_POS[1])


def right_image(event):
    get_right_image(CAMERA_POS[0], CAMERA_POS[1])


def get_above_image(x, y):
    if CAMERA_POS == (0, 11):
        return
    if x == 0:
        get_above_image(5, y)
    elif CAMERAS[x - 1][y] != "":
        load_image(FOLDER + CAMERAS[x - 1][y], x - 1, y, "top")
    else:
        get_above_image(x - 1, y)


def get_below_image(x, y):
    if CAMERA_POS == (0, 11):
        return
    if x == 4:
        get_below_image(-1, y)
    elif CAMERAS[x + 1][y] != "":
        load_image(FOLDER + CAMERAS[x + 1][y], x + 1, y, "bottom")
    else:
        get_below_image(x + 1, y)


def get_left_image(x, y):
    if CAMERA_POS == (0, 11):
        return
    if y == 0:
        get_left_image(x, 12)
    elif CAMERAS[x][y - 1] != "":
        load_image(FOLDER + CAMERAS[x][y - 1], x, y - 1, "left")
    else:
        get_left_image(x, y - 1)


def get_right_image(x, y):
    if CAMERA_POS == (0, 11):
        return
    if y == 11:
        get_right_image(x, -1)
    elif CAMERAS[x][y + 1] != "":
        load_image(FOLDER + CAMERAS[x][y + 1], x, y + 1, "right")
    else:
        get_right_image(x, y + 1)


def reset_cells(cells):
    for i in range(5):  # 5 rows
        for j in range(12):  # 12 columns
            if i == 2 or (i, j) in [
                (0, 0),
                (0, 2),
                (0, 4),
                (0, 6),
                (0, 8),
                (0, 10),
                (1, 1),
                (1, 3),
                (1, 7),
                (1, 9),
                (1, 11),
                (3, 0),
                (3, 2),
                (3, 4),
                (3, 6),
                (3, 8),
                (3, 10),
                (4, 1),
                (4, 3),
                (4, 5),
                (4, 7),
                (4, 9),
                (4, 11),
            ]:
                cell = CTkLabel(grid_frame, bg_color="green", width=50, height=50, text="")
            else:
                cell = CTkLabel(grid_frame, bg_color="black", width=50, height=50, text="")
            cell.grid(row=i, column=j, padx=1, pady=1)
            cells[(i, j)] = cell  # Store reference in dictionary


# Create main window
root = ctk.CTk()
root.title("Capture Stage Data Viewer")
root.geometry("1670x1000")
root.resizable(False, False)
root.configure(fg_color="black")
ctk.set_appearance_mode("dark")

# Create layout frames
left_frame = CTkFrame(root, fg_color="black", width=1000, height=1000)
left_frame.pack(side=ctk.LEFT, padx=10, pady=10)

right_frame = CTkFrame(root, fg_color="black")
right_frame.pack(side=ctk.RIGHT, padx=10, pady=10)

# Image display
image_label = CTkLabel(left_frame, fg_color="black", text="")
image_label.pack()

# Grid above buttons
grid_frame = CTkFrame(right_frame, fg_color="white", corner_radius=0)
grid_frame.pack()

# Dictionary to store cell references
CELLS = {}
reset_cells(CELLS)

# Buttons
button_frame = CTkFrame(right_frame, fg_color="black")
button_frame.pack(pady=10)

btn1 = CTkButton(
    button_frame,
    text="Load Image Directory",
    command=btn1_load_directory,
    fg_color="black",
    width=200,
    height=80,
    border_color="white",
    border_width=4,
    corner_radius=0,
    font=("Modern", 20),
)
btn1.pack(fill=ctk.X, pady=5)

btn2 = CTkButton(
    button_frame,
    text="Rotate Image",
    command=btn2_rotate_image,
    fg_color="black",
    width=200,
    height=80,
    border_color="white",
    border_width=4,
    corner_radius=0,
    font=("Modern", 20),
)
btn2.pack(fill=ctk.X, pady=5)

btn3 = CTkButton(
    button_frame,
    text="Save Rotated Images",
    command=btn3_save_rotation,
    fg_color="black",
    width=200,
    height=80,
    border_color="white",
    border_width=4,
    corner_radius=0,
    font=("Modern", 20),
)
btn3.pack(fill=ctk.X, pady=5)

# Keypresses
root.bind("<Up>", above_image)
root.bind("<Down>", below_image)
root.bind("<Left>", left_image)
root.bind("<Right>", right_image)

# Run the Tkinter main loop
root.mainloop()
