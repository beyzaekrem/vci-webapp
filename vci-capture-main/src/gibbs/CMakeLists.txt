cmake_minimum_required(VERSION 3.27)

project(gibbs LANGUAGES CUDA CXX)

include(FetchContent)

find_package(charonload REQUIRED)
find_package(OpenMP REQUIRED)

# ----------------------------------------------------
#  CORE DEPENDENCIES & SETUP
# ----------------------------------------------------

set(INTERCEPTOR_BUILD_BINDINGS OFF)
add_subdirectory(
    "../../external/vci-websocket/src/interceptor/_C"
    "${CMAKE_BINARY_DIR}/external/vci-websocket"
)

# Disable strip for Debug and RelWithDebInfo
if(DEFINED ENV{GIBBS_BUILD_TYPE})
    set(GIBBS_BUILD_TYPE "$ENV{GIBBS_BUILD_TYPE}")
else()
    set(GIBBS_BUILD_TYPE "RelWithDebInfo")
endif()
set(STRIP_DISABLED_TYPES "Debug" "RelWithDebInfo")
if(GIBBS_BUILD_TYPE IN_LIST STRIP_DISABLED_TYPES)
    message(STATUS "Disabling strip because GIBBS_BUILD_TYPE=${GIBBS_BUILD_TYPE}")
    set(CMAKE_STRIP "")
endif()

# Boost
FetchContent_Declare(Boost URL https://archives.boost.io/release/1.87.0/source/boost_1_87_0.tar.bz2)
FetchContent_GetProperties(boost)
if(NOT boost_POPULATED)
    FetchContent_Populate(boost)
    set(BOOST_INCLUDE_DIR ${boost_SOURCE_DIR})
endif()

# nlohmann/json
FetchContent_Declare(json GIT_REPOSITORY https://github.com/nlohmann/json.git GIT_TAG v3.11.3)
set(JSON_BuildTests OFF CACHE INTERNAL "")
FetchContent_MakeAvailable(json)

# NJPEG (gpu supported jpeg compression)
find_library(NVJPEG_LIBRARY nvjpeg ${CMAKE_CUDA_IMPLICIT_LINK_DIRECTORIES})

# ----------------------------------------------------
#  CAMERA SDK DISCOVERY
#  each SDK should be optional, we should complie even with no SDKs at all.
# ----------------------------------------------------

# --- Basler SKD (pylon+framegrabber) ---
find_package(pylon QUIET)
if (pylon_FOUND)
    set(BASLER_FOUND TRUE)
    message(STATUS "Found Basler pylon SDK. Basler support enabled.")
else()
    set(BASLER_FOUND FALSE)
    message(WARNING "Basler pylon SDK not found. Basler support disabled.")
endif()

# --- XIMEA SDK ---
set(XIMEA_SDK_ROOT "/opt/XIMEA") # Default hint
find_path(XIAPI_INCLUDE_DIR NAMES xiApi.h HINTS ${XIMEA_SDK_ROOT}/include NO_CMAKE_FIND_ROOT_PATH)

if(FALSE)
    set(XIMEA_FOUND TRUE)
    message(STATUS "Found XIMEA SDK. XIMEA support enabled.")
    
    # Add xi_gentl sources and library definition
    set(XI_GENTL_SRC
        /opt/XIMEA/samples/_libs/GenTL/GenTLStream.cpp
        /opt/XIMEA/samples/_libs/GenTL/xi_exception.cpp
        /opt/XIMEA/samples/_libs/GenTL/xi_GenTL.cpp
        /opt/XIMEA/samples/_libs/GenTL/xi_ImgBuffer.cpp
    )
    add_library(xi_gentl STATIC ${XI_GENTL_SRC})
    target_include_directories(xi_gentl PUBLIC /opt/XIMEA/samples/_libs/GenTL/ ${XIAPI_INCLUDE_DIR})
else()
    set(XIMEA_FOUND FALSE)
    message(WARNING "XIMEA SDK not found. XIMEA support disabled.")
endif()

# --- Orbbec SDK ---
find_package(OrbbecSDK CONFIG)
if(OrbbecSDK_FOUND)
    message(STATUS "Found Orbbec SDK. Orbbec support enabled.")
else()
    message(WARNING "Orbbec SDK not found. Orbbec support disabled.")
endif()

# ----------------------------------------------------
#  SOURCE LIST DEFINITION
# ----------------------------------------------------

# Core Source Files
set(SRC_LIST
    ${NV_ENC_SOURCES}
    camera_manager.cpp
    camera.cpp
    util.cpp
    buffer.cpp
    image.cpp
    bindings.cpp
    cameras/simulated/buffer_simulated.cpp
    cameras/simulated/camera_simulated.cpp
    codec/video.cu
    processing/codec.cu
    processing/bayer.cu
    processing/util.cu
    processing/packing.cu
    processing/color_kernels.cu
    processing/color_superkernel.cu
    processing/mono_kernels.cu
    processing/mono_superkernel.cu
    processing/flip.cu
    processing/zoom.cu
    processing/processing_bindings.cpp
    io/cache.cpp
    tasks/capture.cpp
    tasks/matting.cpp
    tasks/ring_buffer_capture.cpp
    tasks/livestreams.cpp
    tasks/record_capture.cpp
    ${INTERCEPTOR_BINDINGS}
)

# Additional Camera SKD source file (if SKD can be found)
if(BASLER_FOUND)
    list(APPEND SRC_LIST cameras/basler/basler_camera.cpp cameras/basler/basler_buffer.cpp)
endif()

if(XIMEA_FOUND)
    list(APPEND SRC_LIST cameras/ximea/buffer_ximea.cpp cameras/ximea/camera_ximea.cpp cameras/ximea/xi_util.cpp)
endif()

if(OrbbecSDK_FOUND)
    list(APPEND SRC_LIST cameras/orbbec/orbbec_camera.cpp cameras/orbbec/orbbec_buffer.cpp)
endif()


# ----------------------------------------------------
#  TARGET DEFINITION AND CONFIGURATION
# ----------------------------------------------------

if(charonload_FOUND)
    # create Target!
    charonload_add_torch_library(${TORCH_EXTENSION_NAME} MODULE)
    target_sources(${TORCH_EXTENSION_NAME} PRIVATE ${SRC_LIST})

    # Core Include Directories
    target_include_directories(
        ${TORCH_EXTENSION_NAME} PRIVATE
        .
        ${BOOST_INCLUDE_DIR}
    )

    # Core Link Libraries
    target_link_libraries(${TORCH_EXTENSION_NAME} PRIVATE
        interceptor
        OpenMP::OpenMP_CXX
        nlohmann_json::nlohmann_json
        ${NVJPEG_LIBRARY}
    )
    
    # Conditional Camera SDK Target Configuration
    if(BASLER_FOUND)
        target_compile_definitions(${TORCH_EXTENSION_NAME} PRIVATE ENABLE_BASLER_SUPPORT)
        target_link_libraries(${TORCH_EXTENSION_NAME} PRIVATE pylon::pylon)
    endif()

    if(XIMEA_FOUND)
        target_compile_definitions(${TORCH_EXTENSION_NAME} PRIVATE ENABLE_XIMEA_SUPPORT)
        target_include_directories(${TORCH_EXTENSION_NAME} PRIVATE ${XIAPI_INCLUDE_DIR})
        target_link_libraries(${TORCH_EXTENSION_NAME} PRIVATE xi_gentl m3api)
    endif()

    if(OrbbecSDK_FOUND)
        target_compile_definitions(${TORCH_EXTENSION_NAME} PRIVATE ENABLE_ORBBEC_SUPPORT)
        target_link_libraries(${TORCH_EXTENSION_NAME} PRIVATE ob::OrbbecSDK)
    endif()


    target_link_options(${TORCH_EXTENSION_NAME} PRIVATE -Wl,--no-as-needed)
    # Include debug symbols in Debug and RelWithDebInfo builds, skip optimization in Debug
    set_target_properties(${TORCH_EXTENSION_NAME} PROPERTIES
        COMPILE_OPTIONS
        "$<$<CONFIG:Debug>:-g;-O0;-fno-omit-frame-pointer>;$<$<CONFIG:RelWithDebInfo>:-g;-fno-omit-frame-pointer>"
    )
endif()