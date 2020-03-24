import serial
import os
import subprocess

import gphoto2 as gp

"""
List all the files on the camera
camera - gp_camera object
path - path on the camera where photos are stored

"""
def list_files(camera, path='/'):
    result = []
    # get files
    for name, value in gp.check_result(
            gp.gp_camera_folder_list_files(camera, path)):
        result.append(os.path.join(path, name))
    # read folders
    folders = []
    for name, value in gp.check_result(
            gp.gp_camera_folder_list_folders(camera, path)):
        folders.append(name)
    # recurse over subfolders
    for name in folders:
        result.extend(list_files(camera, os.path.join(path, name)))
    return result

"""
Capture a single image and store in path
camera - gp_camera object
path - path on the Raspberry Pi where captured images are stored

"""
def camera_capture_image(camera, path='/tmp'):
    # initialize camera
    gp.check_result(gp.gp_camera_init(camera))
    # capture a image
    file_path = gp.check_result(gp.gp_camera_capture(
            camera, gp.GP_CAPTURE_IMAGE))
    # store a image
    target = os.path.join(path, file_path.name)
    camera_file = gp.check_result(gp.gp_camera_file_get(
            camera, file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL))
    gp.check_result(gp.gp_file_save(camera_file, target))
    # subprocess.call(['xdg-open', target])
    # exit camera
    gp.check_result(gp.gp_camera_exit(camera))

"""
Capture light field as a set of images and store in path
camera - gp_camera object
ser - Serial object for serial communication
n_views - number of views for the capture
n_exposures - number of exposures for the camera bracketing mode

"""
def camera_capture_light_field(camera, ser, n_views, n_exposures, stops=2.0,
            base_exposure=0.01, ext='.arw'):
    # initialize camera location
    ser.write(b'm0')
    # capture process
    for capture_location in range(n_views):
        # initialize camera
        context = gp.Context()
        camera.init(context)
        config = camera.get_config(context)
        shutterspeed_node = config.get_child_by_name('shutterspeed')
        # write to SD card
        capture_target_node = config.get_child_by_name('capturetarget')
        capture_target_node.set_value('1')
        # set ISO
        iso_node = config.get_child_by_name('iso')
        iso_node.set_value('100')

        # wait for camera to stop moving and trigger camera capture
        process = ser.readline()
        # capture HDR stack
        for file_number in range(n_exposures):
            # file format: capt-<sequence>-<distance(mm)>[<exposure(EV)>].arw
            # e.g. capt-001-0100[-2.0].arw
            camera_file = "capt-{:0>3d}-{:0>4d}[{:+.1f}]".format(
                            capture_location*n_exposures + file_number,
                            int(capture_location*(1000/(n_views-1))),
                            stops*file_number)
                        + ext
            camera.file_set_info('/', camera_file, gp.GP_FILE_TYPE_NORMAL, context)
            # update exposure time and capture
            shutterspeed_node.set_value(str(base_exposure*2**(stops*file_number)))
            camera.set_config(config)
            camera.capture(gp.GP_CAPTURE_IMAGE)
            # Wait till capture is done
            event = camera.wait_for_event(1)[0]
            while event != gp.GP_EVENT_FILE_ADDED:
                event = camera.wait_for_event(1)[0]
        # move to the next location
        if capture_location is not n_views-1:
            ser.write(b'm' + str((capture_location+1)*(1000//(n_views-1))).encode('UTF-8'))
        # exit camera
        camera.exit()
    # return to initial location
    ser.write(b'm0')
