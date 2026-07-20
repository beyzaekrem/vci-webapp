#ifndef CAPTN_XIMEA_BUFFER_H
#define CAPTN_XIMEA_BUFFER_H

#include <fcntl.h>
#include <unistd.h>
#include <fstream>
#include <map>
#include <mutex>
#include <stdexcept>
#include <vector>

#include "buffer.h"
#include "util.h"
#include "xi_include.h"

/**
 * @brief A buffer entry using the GenTL API.
 *
 * Upon initialization the buffer is:
 * - allocated,
 * - announced to the DS_HANDLE,
 * - and queued.
 *
 * Once the EVENT_NEW_BUFFER happens on this buffer, FrameWasCaptured() must be
 * called to update the information, lock the buffer and make it valid.
 * After this, the buffer needs to be unlocked in order to be queued again,
 * at which point it becomes invalid, since we cannot control when it will be
 * filled again.
 *
 * Note that the buffer has a lock counting mechanism, so multiple entities
 * can use it. Once all locks have been released, the buffer automatically
 * queues itself. Locking and unlocking is only available on unqueued buffers,
 * and will do nothing on a queued buffer.
 *
 * Before destruction, the buffer needs to be unqueued. This is only possible
 * by flushing the whole queue and notifying all buffers using SetUnqueued.
 * After that, Revoke should be called. This is also done automatically in the
 * destructor, but only Revoke can throw errors.
 *
 * TODO: It might be a better idea to handle the BufferEntry using a BufferView
 * class using a shared_ptr that handles the locking/unlocking upon destruction.
 */
class XimeaBufferEntry : public BufferEntry {
 public:
  /**
   * @brief Construct a new Buffer Entry object
   *
   * @param info Meta information of the assigned camera
   * @param stream_handle Stream handle of the camera
   * @param payload_bytes Size of the buffer in bytes
   *
   * @throw GenTLError if a GenTL call fails
   */
  XimeaBufferEntry(const CameraInfo* info, const GenTL::DS_HANDLE stream_handle, int payload_bytes);
  ~XimeaBufferEntry() override;

  /**
   * @brief Manually queues the buffer.
   *
   * Only needs to be called when the queue was flushed and the buffer should
   * be queued again. Remember to call SetUnqueued() after flushing.
   * Also sets the buffer invalid.
   *
   * @throw AlreadyInQueueError If the buffer is still queued when called.
   * @throw BufferIsLockedError If the buffer is still locked.
   * @throw GenTLError if a GenTL call fails
   */
  void Queue();
  /**
   * @brief Needs to be called once a new frame is captured in this buffer.
   *
   * - Updates entry info with data from accquired frame.
   * - Sets is_queued_ to false.
   * - Sets valid_ to true.
   * - Sets the lock count to 1.
   *
   * @throw GenTLError if a GenTL call fails.
   * @throw TransportInterrupted if the transport was interrupted.
   */
  void FrameWasCaptured();
  /**
   * @brief Increases the lock count by one.
   *
   * Only works on unqueued and valid buffers.
   *
   * @return True if the locking worked, false when not.
   */
  bool Lock();
  /**
   * @brief Decreases the lock count by one and requeues the buffer if possible.
   *
   * Only does something if the lock count is greater than zero. Once the
   * counter reaches zero, the buffer will be requeued and becomes invalid.
   *
   * @throw GenTLError if a GenTL call fails.
   */
  void Unlock() override;
  /**
   * @brief Announces the buffer.
   *
   * @throw GenTLError if a GenTL call fails.
   */
  void Announce();
  /**
   * @brief Revokes the buffer. Should be called before destruction.
   *
   * @throw GenTLError if a GenTL call fails.
   */
  void Revoke();
  /**
   * @brief If the buffer is currently queued.
   *
   * @return true if the buffer is queued.
   */
  bool IsQueued() const;
  /**
   * @brief If the buffer is currently locked.
   *
   * @return true if the buffer is locked.
   */
  bool IsLocked() const;
  /**
   * @brief Pointer to the raw image data of length payload_bytes.
   *
   * @return char* to buffer.
   */
  const char* Buffer() const override;
  /**
   * @brief Size of the payload/buffer in bytes
   *
   * @return size_t the size
   */
  size_t PayloadBytes() const override;
  /**
   * @brief Pointer to the buffer meta data.
   *
   * @return const EntryInfo* meta data.
   */
  const EntryInfo* Info() const override;
  /**
   * @brief GenTL buffer handle
   *
   * @return GenTL::BUFFER_HANDLE the handle
   */
  GenTL::BUFFER_HANDLE Handle();
  /**
   * @brief Camera information
   *
   * @return CamerInfo the camera information
   */
  const CameraInfo* GetCameraInfo() const override;
  /**
   * @brief Writes all bytes in buffer to output stream
   *
   * @param output_file_stream stream to write to
   * @return size_t stream position the data was written to (i.e. the start)
   */
  size_t WriteTo(std::ofstream& output_file_stream) const override;
  /**
   * @brief Writes all bytes in buffer to file pointer
   *
   * @param fp C file pointer
   * @return size_t file position the data was written to (i.e. the start)
   */
  size_t WriteTo(int fp) const override;

 private:
  void GetBufferInfo(GenTL::BUFFER_INFO_CMD cmd, GenTL::INFO_DATATYPE datatype, void* value, size_t value_size) const;
  bool GetBufferInfoBool(GenTL::BUFFER_INFO_CMD cmd) const;
  size_t GetBufferInfoSizeT(GenTL::BUFFER_INFO_CMD cmd) const;
  uint32_t GetBufferInfoUInt32(GenTL::BUFFER_INFO_CMD cmd) const;
  uint64_t GetBufferInfoUInt64(GenTL::BUFFER_INFO_CMD cmd) const;
  char* GetBufferInfoPtr(GenTL::BUFFER_INFO_CMD cmd) const;

  /// Info of the camera associated with this buffer.
  const CameraInfo* camera_info_;
  /// GenTL data stream handle managed by the camera.
  const GenTL::DS_HANDLE stream_handle_;
  /// Buffer handle managed by this class.
  GenTL::BUFFER_HANDLE handle_;
  /// Pointer to the buffer allocated upon initialization.
  char* data_;
  /// Size of the buffer in bytes.
  const size_t payload_bytes_;
  /// Meta data of the captured frame.
  EntryInfo info_;
  /// How many times the buffer has been locked.
  int lock_counter_;
  /// To protect state changes
  std::recursive_mutex state_mutex_;
};

/**
 * @brief Manages the frame buffer for a single camera using the GenTL API
 *
 * Since each frame buffer is tightly integrated with a camera, none of the
 * functions are thread safe. It is the task of the camera to ensure that.
 */
class FrameBuffer {
 public:
  FrameBuffer(const CameraInfo* info, int length = 8);
  ~FrameBuffer();

  void InitializeStream(GenTL::DS_HANDLE stream_handle);
  void CloseStream();

  void Start();
  void Stop();
  /**
   * @brief
   *
   * @param timeout_ms
   * @return BufferEntry*
   *
   * @throw BufferTimeout
   */
  XimeaBufferEntry* CaptureNext(int timeout_ms = 200);

  void SetLength(int length);
  void SetPayload(int payload_bytes);
  void Allocate();
  void Free();
  void ForceQueue();
  /**
   * @brief Number of Buffers that are queued (input, being filled, output)
   */
  int NumQueued();

 private:
  const CameraInfo* camera_info_;

  /// Target size of the frame buffer (number of frames)
  int length_;
  /// Payload per frame in bytes
  int payload_bytes_;

  GenTL::DS_HANDLE stream_handle_;
  GenTL::EVENT_HANDLE event_handle_;

  std::vector<XimeaBufferEntry*> buffer_;
  std::map<GenTL::BUFFER_HANDLE, XimeaBufferEntry*> buffer_map_;
};
#endif  // CAPTN_BUFFER_H
