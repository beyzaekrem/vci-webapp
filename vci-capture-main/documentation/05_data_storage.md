## Persistent Data

We store persistent data in a docker volume `vci_capture_persistent` which is mounted under `/srv/vci-capture-persistent`.
On the host system, it can be found under `/var/lib/docker/volumes/vci_capture_persistent/_data/`.
It contains the following directories:

- `background`: Raw background images and meta data
- `capture`: Capture meta data
- `config`: Json configs
- `logs`: Log files