import tests.orbbec.helpers as h


def main():

    cams, orbbec_cameras, ximea_cameras = h.enumerate_cameras()
    h.set_color_mode(orbbec_cameras)
    h.assign_roles(orbbec_cameras)
    h.start_orbbec(orbbec_cameras)
    h.capture_loop(orbbec_cameras, n=100)
    h.stop_orbbec(orbbec_cameras)


if __name__ == "__main__":
    main()
