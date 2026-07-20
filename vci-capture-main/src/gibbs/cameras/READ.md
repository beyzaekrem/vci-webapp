Specific implementations of camera APIs from various manufacturers.
All **camera types are optional**. The server should still build and run when 
your SDK is not installed and/or your camera type is not connected.

# Add a new camera type:
Implement camera.cpp and buffer.cpp to add a new camera by a specific manufacturer.
(Refer to camera_ximea.cpp and buffer_ximea.cpp.)

### CMake
Adjust **CMakeLists.txt** to add the SDK you need.
See the camera types XIMEA or BASLER for reference in CMakeLists.txt.
Important points:

* Search for your SDK - do not crash if it can't be found.
* Create a global variable with the found/notfound state
* Add your .cpp files - only if your SDK is found
* Link your SDK Library - only if the SDK was found

### camera_manager
Add your new camera type in **camera_manager.cpp**.
Create a new CameraFactory for your type.
Use the global found/notfound variable (from CMake) to control if your CameraFactory gets defined and used.

### (no) python binding
No not bind your exact camera type to python through bindings.cpp.
This creates a hard dependency on your SDK!
Instead stick to the general camera functions. Set custom parameters through SetParameterInt etc.
If you have to, add a new function to the general camera.cpp. Keep in mind that all other cameras need to implement the same function!

### specific util and errors
Keep all SDK specific util and error stuff inside your cameras subfolder.
(Similar to ximea/xi_util)