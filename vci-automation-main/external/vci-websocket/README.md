# vci-websocket

We want to avoid copy overhead when sending and receiving data. Therefore
all data passed to a send method will not be copied and instead send directly.
To combine easy to use formats with raw byte data, we add the option to send
multiple payloads in a single message. It is up to the user to decide how to
interpret the packs.


## Installation

### Requirements

apt install -y libssl-dev

If you get problems regarding the gcc/g++ version, use update-alternatives to switch to a different version.

### Setup

`pip install .`
or
`pip install -e .`

## Handler

## Path Handler

```python
@interceptor.path_handler("MY_PATH")
    def my_path_handler(self, message: interceptor.MessageIn) -> None:
      """

      """
```

## Design

### Header 
The library adds a header to each message which is bson encoded.
The first 4 bytes of this header indicate the total size of the header which
contains the following data:

```
- TYPE: int
- ID: int
- PATH: string (optional)
- ERROR: string (optional)
- META: json (optional)
- PAYLOAD: List
  - SIZE: int
  - TYPE: string (maybe?)
  - META (optional)
```

An example header for a message with two payloads would look like this:

```
{
  "TYPE": 3, // (StandardMessage)
  "ID": 1234,
  "PATH": "SETUP_ALL_THE_THINGS",
  "PAYLOAD": [
    {
      "SIZE": 4586,
      "META": "Some Info"
    },
    {
      "SIZE": 42,
    },
  ],
}
```
### TESTING

For testing we use pytest. Install pytest by running `pip install pytest`.

To run all test just run `pytest`.
To run a specific test you can use `pytest yourTestFile.py::YourTestClass::YourTestFunction


## TODO

### Queues

Add receive queue and endpoint overload exception

### Custom exceptions

Registering custom exceptions

### Numpy array and pytorch tensor payloads

Wrapper to send numpy arrays and pytorch tensors with all meta info
