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
def camera_capture_light_field(camera, ser, n_views, n_exposures, stops, path,
            base_exposure=0.01, ext='.arw'):
    # initialize camera location
    ser.write(b'm0')
    # capture process
    for capture_location in range(n_views):
        # initialize camera
        context = gp.Context()
        inform_user = True
        while True:
            try:
                camera.init(context)
            except gp.GPhoto2Error as e:
                if inform_user:
                    print('Waiting for camera to be connected and switched on')
                    inform_user = False
                if e.code == gp.GP_ERROR_MODEL_NOT_FOUND:
                    sleep(2)
                    continue
                raise
            break
        config = camera.get_config(context)
        shutterspeed_node = config.get_child_by_name('shutterspeed')
        # # write to SD card - not supported by Sony alpha series
        # capture_target_node = config.get_child_by_name('capturetarget')
        # capture_target_node.set_value('1')
        # set ISO
        iso_node = config.get_child_by_name('iso')
        iso_node.set_value('100')

        # wait for camera to stop moving and trigger camera capture
        process = ser.readline()
        # capture HDR stack
        for file_number in range(n_exposures):
            # update exposure time and capture
            shutterspeed_node.set_value(str(base_exposure*2**(stops*file_number)))
            camera.set_config(config)
            file_path = camera.capture(gp.GP_CAPTURE_IMAGE)
            
            # Save file on pi
            # file format: capt_<view>_<exposure>.<extension>
            # Ex. capt_001_0.arw
            target = os.path.join(path, f'capt_{capture_location:03}_{file_number}.{ext}')
            camera_file = camera.file_get(file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL)
            camera_file.save(target)
        
        # move to the next location
        if capture_location is not n_views-1:
            ser.write(b'm' + str((capture_location+1)*(1000//(n_views-1))).encode('UTF-8'))
        # exit camera
        camera.exit()
    # return to initial location
    ser.write(b'm0')
