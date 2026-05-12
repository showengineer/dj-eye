# DeckClock

![single player screenshot](screenshot-single.png)

DeckClock is a ProDJ link monitor forked from [python-prodj-link](https://github.com/flesniak/python-prodj-link) that was further built for use in specifically for live event production. It is able to output linear timecode with configurable output and player. On Windows, it supports ASIO devices (if correct drivers are installed).

## Getting Started

These instructions describe necessary work to be done before being able to run the project. The program has successfully ran under Windows and Ubuntu. Other linux distributions should work fine. I cannot guarantee anything about macOS, however.

### Prerequisites

DeckClock is written in Python 3. The minimum required version is Python 3.13. It also requires
[Construct](https://pypi.python.org/pypi/construct) **(Version 2.9 or later)**,
[PyQt5](https://pypi.python.org/pypi/PyQt5),
[PyOpenGL](https://pypi.org/project/PyOpenGL/),
[netifaces](https://pypi.org/project/netifaces),
[numpy](https://pypi.org/project/numpy),
[scipy](https://pypi.org/project/scipy) and
[sounddevice](https://pypi.org/project/sounddevice).

[Pipenv](https://pypi.org/project/pipenv) is used for managing the virtual environment. 

The packages may be installed using `pipenv update`, and getting into the virtual environment with `pipenv shell` 

### Testing
```
python3 test_runner.py
```

### Network configuration

You need to be on the same Ethernet network as the players are discovered using broadcasts.
The players will aquire IPs using DHCP if a server is available, otherwise they fall back to IPv4 autoconfiguration.
If there is no DHCP server on your network, make sure you assign a IP address inside 169.254.0.0/16 to yourself, for example using NetworkManager or avahi-autoipd.

You can test your setup using wireshark or tcpdump to see if you receive keepalive broadcast on port 50000.

## Usage
The program displays some information about the tracks on every player, including metadata, artwork, current BPM, waveform and preview waveform.
Waveforms are rendered using OpenGL through Qt, thus you need an OpenGL 2.0 compatible graphics driver.
It is also possible to browse media and load these tracks into players remotely.
Additionally, you can download tracks from remote players, either directly when loaded or from the media browser.

    ./deckclock.py

or using pipenv:

    pipenv run deckclock.py

![two players screenshot with browser](screenshot-full.png)

## Bugs & Contributing
This is still very much in beta stage.
The program may freeze your players due to network congestion, although as of now I have not encountered that yet.
Be especially careful with DJM-A9 mixers in your network, as my colleagues have pointed out that these are problematic with ProDJ link monitors.

If you experience any errors or have additional features, feel free to open an issue or pull request.
The program has been already **successfully tested** the script against the following players/mixers:

* Pioneer CDJ 2000
* Pioneer CDJ 2000 Nexus
* Pioneer CDJ 2000 NXS2
* Pioneer XDJ 1000
* Pioneer DJM 900 Nexus
* Pioneer DJM 900 NXS2
* Pioneer CDJ 3000
* Pioneer DJM-A9

## Acknowledgments
* The [python-prodj-link](https://github.com/flesniak/python-prodj-link) project, where this is largely based on.
* A lot of information from [dysentery](https://github.com/brunchboy/dysentery)
* And some info from Austin Wright's [libpdjl](https://bitbucket.org/awwright/libpdjl)

## License
DeckClock is based on python-prodj-link, originally licensed under the Apache License,
Version 2.0. Portions of this repository are derived from that project and remain subject
to the original Apache 2.0 license and notices.

ShowEngineering names, logos, and other branding assets included in this repository are
copyrighted material and are not licensed for reuse under the Apache License.

See LICENSE and NOTICE for details.

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
