# Atem Gateway

**Description**:  A micro service for controlling [ATEM](https://www.blackmagicdesign.com/products/atemtelevisionstudio) video switchers.

  - **Technology stack**: Python, hmux
  - **Status**:  Production

## Dependencies

- Depends on python 2.7
- It uses the hmux messaging protocol.
- Needs [daemonctl](https://github.com/SVT/daemonctl) to run.

## Installation

Place folder in /usr/local/scripts and run:
 - daemonctl enable atemgateway
 - daemonctl start atemgateway

## Configuration

```
Place config in /usr/local/etc/atemgateway.conf
Example config:
server = atem1.local
hmuxport = 12345 # Port to listen on
statusdest = VideoMixer # Destination in hmux
```

## Usage
Connect to the hmux port and send commands enclosed in \x01 and \x00
Arguments are seperated with ":"

Destinations:
- HB - Program out
- BS - Over shoulder out

Commands:
- CUE:dest:source - Set preview source
- TAKE:dest:source:mixtime:mix - Mix/Cut/Wipe a source to destination
- KEY:me:keyer:enable - Enable or disable upstream key
- DSK:keyer:enable - Enable or disable downstream key
- DSKSOURCES:keyer:fill source:key source - Set fill and key sources for dsk
- DSKLUMA:keyer:premultiply:clip:gsin:invert - Set Luma setting for DSK
- VOLUME:source:volume - Set audio volume for a source
- MASTERVOLUME:volume - Set master audio volume
- MOVEVOLUME:source:volume:frames - Move volume to position taking frames time


Ex, Mix source 1 to HB (pgm out) using 12 frames:
```
\x01TAKE:HB:1:12:M\00
```

## Known issues

Every atem firmware works different, all firmwares might not be compatible

## Getting help
If you have questions, concerns, bug reports, etc, please file an issue in this repository's Issue Tracker.


## Getting involved
Feature request with documentation, fixes, new features and general beutification is welcome.

----

## Open source licensing info
Copyright: SVT 2018
GNU General Public License version 3
[LICENSE](LICENSE)


----

## Credits and references

Protocol documentation found at:
 http://skaarhoj.com/fileadmin/BMDPROTOCOL.html

Videomodes taken from libqatemcontrol
 https://github.com/petersimonsson/libqatemcontrol/blob/master/qatemconnection.cpp

## Primary Maintainer

Andreas Åkerlund https://github.com/thezulk  
