# Domoticz Python Plugin for Onkyo Receivers
#
# Author: jorgh
#
"""
<plugin key="Onkyo" name="Onkyo AV Receiver" author="jorgh" version="0.2.5" wikilink="https://github.com/jorgh6/domoticz-onkyo-plugin/wiki" externallink="https://github.com/jorgh6/domoticz-onkyo-plugin">
  <params>
    <param field="Mode6" label="Debug" width="75px">
      <options>
        <option label="True" value="Debug"/>
        <option label="False" value="Normal"  default="True" />
      </options>
    </param>
  </params>
</plugin>
"""
import Domoticz
import socket
import xml.etree.ElementTree as XMLTree

#DEFINES -- Sort of ;-)
MESSAGE_HEADER_1 = 'ISCP\x00\x00\x00\x10\x00\x00\x00'
MESSAGE_HEADER_2 = '\x01\x00\x00\x00'
MESSAGE_TRAILER = '\x0D\x0A'
MESSAGE_DISCOVER = '!xECNQSTN'
MESSAGE_RECEIVER_INFORMATION = '!1NRIQSTN'

MESSAGE_POWER = '!1PWR'
MESSAGE_MUTE = '!1AMT'
MESSAGE_VOLUME = '!1MVL'
MESSAGE_SOURCE = '!1SLI'
MESSAGE_LISTENINGMODE = '!1LMD'
MESSAGE_TUNERPRESET = '!1PRS'

MESSAGE_POWER2 = '!1ZPW'
MESSAGE_MUTE2 = '!1ZMT'
MESSAGE_VOLUME2 = '!1ZVL'
MESSAGE_SOURCE2 = '!1SLZ'

MESSAGE_POWER3 = '!1PW3'
MESSAGE_MUTE3 = '!1MT3'
MESSAGE_VOLUME3 = '!1VL3'
MESSAGE_SOURCE3 = '!1SL3'

MESSAGE_POWER4 = '!1PW4'
MESSAGE_MUTE4 = '!1MT4'
MESSAGE_VOLUME4 = '!1VL4'
MESSAGE_SOURCE4 = '!1SL4'

BUFFER_SIZE = 4096
MAINPOWER = 1
MAINSOURCE = 2
MAINVOLUME = 3
MAINLISTENINGMODE = 4
TUNERPRESETS = 5
ZONE2POWER = 6
ZONE2SOURCE = 7
ZONE2VOLUME = 8
ZONE3POWER = 9
ZONE3SOURCE = 10
ZONE3VOLUME = 11
ZONE4POWER = 12
ZONE4SOURCE = 13
ZONE4VOLUME = 14

UDP_PORT = 60128
EOF = 26
NA = -1

class Onkyo:
  enabled = False
  objConnection = None

  def __init__(self):
    self.blDiscoverySocketCreated = False    # Has the UDP socket for the Onkyo discovery protocol been created.
    self.blDiscoveryRequestSend = False      # Has the Discovery Request UDP package been send.
    self.blDiscoverySucces = False           # Has the Discovery proces succeeded
    self.blConnectInitiated = False          # Have we initiated the connection request
    self.blConnected = False                 # Are we connected
    self.XMLProcessed = False                # Have we processed the XML
    self.blCheckedDevices = False            # Have the Domoticz devices been checked
    self.blCheckedStates = False             # Have we fetched the state after startup
    self.blInitDone = False                  # Has the initialization proces completed
    self.sockUDP = ''                        # Used for storing the UDP socket
    self.strIPAddress = ''                   # The IP address of the Onkyo Receiver
    self.strPort = ''                        # Contains the TCP port number to connect to
    self.blDebug = False                     # Is debugging turned on
    self.strInputBuffer = ''                 # In this buffer we store incomming data
    self.bInputBuffer = b''
    self.XMLRoot = None                      # Used to store the XML configuration data of the reciever
    self.intMainMaxVolume = 80
    self.intZone2MaxVolume = 80
    self.intZone3MaxVolume = 80
    self.intZone4MaxVolume = 80
    self.XMLBuffer = ''
    return

  def onStart(self):
    if Parameters["Mode6"] == "Debug":
      self.blDebug = True
      Domoticz.Debugging(1)
    
    if (self.blDebug ==  True):
      Domoticz.Log("Onkyo: onStart called")
    Domoticz.Heartbeat(2)                   # Lower hartbeat interval, to speed up the initialization. 

  def onStop(self):
    if (self.blDebug ==  True):
      Domoticz.Log("Onkyo: onStop called")

  def onConnect(self, Connection, Status, Description):
    if (self.blDebug ==  True):
      Domoticz.Log("onConnect called")
    self.blConnected = True                 # We are now connected

  def onMessage(self, Connection, Data):
    if (self.blDebug ==  True):
      Domoticz.Log("onMessage called")
      Domoticz.Log("We received "+str(len(Data))+" bytes of data")
    self.bInputBuffer = b''.join([self.bInputBuffer, Data])       # We add the received data to the inputbuffer.
    while (self.checkInputBuffer() == True):                      # Check if we have one or more complete frames in the input buffer
      if (self.blDebug ==  True):
        Domoticz.Log('We have a eISCP frame to process')
      self.processeISCPFrame()

  def onCommand(self, Unit, Command, Level, Hue):
    if (self.blDebug ==  True):
      Domoticz.Log("Onkyo: onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

    if (Unit==MAINPOWER):
      # Main Power
      if str(Command)=='On':
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_POWER+'01'))
      if str(Command)=='Off':
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_POWER+'00'))

    if (Unit==MAINVOLUME):
      # Main Volume
      if (Command=='Set Level'):
        strVolume = hex(int((self.intMainMaxVolume/100)*Level))[2:]
        if len(strVolume) == 1:
          strVolume = '0'+strVolume
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_VOLUME+strVolume))
      if (Command=='On'):
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_MUTE+'00'))
        #Unmute
      if (Command=='Off'):
        #Mute
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_MUTE+'01'))

    if (Unit==MAINSOURCE):
      #Input Selector
      dictOptions = Devices[MAINSOURCE].Options
      listLevelNames = dictOptions['LevelNames'].split('|')
      strSelectedName = listLevelNames[int(int(Level)/10)] 
      if (self.blDebug ==  True):
        Domoticz.Log('Main Source Selected: '+strSelectedName)
      for selector in self.XMLRoot.find('device').find('selectorlist'):
        if (selector.get('name')==strSelectedName):
          strId = selector.get('id').upper()
          self.objConnection.Send(Message=createISCPFrame(MESSAGE_SOURCE+strId))

    if (Unit==MAINLISTENINGMODE):
      #Listening Mode Selector
      dictOptions = Devices[MAINLISTENINGMODE].Options
      listLevelNames = dictOptions['LevelNames'].split('|')
      strSelectedName = listLevelNames[int(int(Level)/10)]
      if (self.blDebug ==  True):
        Domoticz.Log('Main Listening Mode Selected: '+strSelectedName)
      strCode = None
      for selector in self.XMLRoot.find('device').find('controllist'):
        if (selector.get('id')=='LMD '+strSelectedName):
          strCode = selector.get('code')
      if (strCode == None):
         Domoticz.Log('Trying discovered listening modes')
         strCode = strSelectedName[strSelectedName.find('[')+1:]
         strCode = strCode[:strCode.find(']')]
         Domoticz.Log('Found: '+strCode)
      if strCode != None:
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_LISTENINGMODE+strCode))

    if (Unit==TUNERPRESETS):
      #Tuner Preset Selector
      dictOptions = Devices[TUNERPRESETS].Options
      listLevelNames = dictOptions['LevelNames'].split('|')
      strSelectedName = listLevelNames[int(int(Level)/10)]
      if (self.blDebug ==  True):
        Domoticz.Log('Tuner Preset Selected: '+strSelectedName)
      intTunerPreset = int(strSelectedName[0:strSelectedName.find(' ')])
      if (self.blDebug ==  True):
        Domoticz.Log('Tuner Preset Number: '+str(intTunerPreset))
      strTunerPreset = hex(intTunerPreset)[2:]
      if len(strTunerPreset) == 1:
        strTunerPreset = '0'+strTunerPreset
      self.objConnection.Send(Message=createISCPFrame(MESSAGE_TUNERPRESET+strTunerPreset))

    if (Unit==ZONE2POWER):
      # Zone2 Power
      if str(Command)=='On':
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_POWER2+'01'))
      if str(Command)=='Off':
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_POWER2+'00'))

    if (Unit==ZONE2VOLUME):
      # Zone 2 Volume
      if (Command=='Set Level'):
        strVolume = hex(int((self.intZone2MaxVolume/100)*Level))[2:]
        if len(strVolume) == 1:
          strVolume = '0'+strVolume
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_VOLUME2+strVolume))
      if (Command=='On'):
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_MUTE2+'00'))
        #Unmute
      if (Command=='Off'):
        #Mute
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_MUTE2+'01'))

    if (Unit==ZONE2SOURCE):
      #Zone 2 input Selector
      dictOptions = Devices[ZONE2SOURCE].Options
      listLevelNames = dictOptions['LevelNames'].split('|')
      strSelectedName = listLevelNames[int(int(Level)/10)]
      Domoticz.Log('Zone 2 Source Selected: '+strSelectedName)
      for selector in self.XMLRoot.find('device').find('selectorlist'):
        if (selector.get('name')==strSelectedName):
          strId = selector.get('id').upper()
          self.objConnection.Send(Message=createISCPFrame(MESSAGE_SOURCE2+strId))

    if (Unit==ZONE3POWER):
      # Zone2 Power
      if str(Command)=='On':
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_POWER3+'01'))
      if str(Command)=='Off':
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_POWER3+'00'))

    if (Unit==ZONE3VOLUME):
      # Zone 3 Volume
      if (Command=='Set Level'):
        strVolume = hex(int((self.intZone3MaxVolume/100)*Level))[2:]
        if len(strVolume) == 1:
          strVolume = '0'+strVolume
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_VOLUME3+strVolume))
      if (Command=='On'):
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_MUTE3+'00'))
        #Unmute
      if (Command=='Off'):
        #Mute
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_MUTE3+'01'))

    if (Unit==ZONE3SOURCE):
      #Zone 3 input Selector
      dictOptions = Devices[ZONE3SOURCE].Options
      listLevelNames = dictOptions['LevelNames'].split('|')
      strSelectedName = listLevelNames[int(int(Level)/10)]
      Domoticz.Log('Zone 3 Source Selected: '+strSelectedName)
      for selector in self.XMLRoot.find('device').find('selectorlist'):
        if (selector.get('name')==strSelectedName):
          strId = selector.get('id').upper()
          self.objConnection.Send(Message=createISCPFrame(MESSAGE_SOURCE3+strId))

    if (Unit==ZONE4POWER):
      # Zone4 Power
      if str(Command)=='On':
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_POWER4+'01'))
      if str(Command)=='Off':
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_POWER4+'00'))

    if (Unit==ZONE4VOLUME):
      # Zone 4 Volume
      if (Command=='Set Level'):
        strVolume = hex(int((self.intZone4MaxVolume/100)*Level))[2:]
        if len(strVolume) == 1:
          strVolume = '0'+strVolume
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_VOLUME4+strVolume))
      if (Command=='On'):
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_MUTE4+'00'))
        #Unmute
      if (Command=='Off'):
        #Mute
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_MUTE4+'01'))

    if (Unit==ZONE4SOURCE):
      #Zone 4 input Selector
      dictOptions = Devices[ZONE4SOURCE].Options
      listLevelNames = dictOptions['LevelNames'].split('|')
      strSelectedName = listLevelNames[int(int(Level)/10)]
      Domoticz.Log('Zone 4 Source Selected: '+strSelectedName)
      for selector in self.XMLRoot.find('device').find('selectorlist'):
        if (selector.get('name')==strSelectedName):
          strId = selector.get('id').upper()
          self.objConnection.Send(Message=createISCPFrame(MESSAGE_SOURCE4+strId))

  def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
    if (self.blDebug ==  True):
      Domoticz.Log("Onkyo: Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

  def onDisconnect(self, Connection):
    if (self.blDebug ==  True):
      Domoticz.Log("onDisconnect called")
    self.blDiscoverySocketCreated = False    # We reset the status to it's initial settings to start all over again.
    self.blDiscoveryRequestSend = False
    self.blDiscoverySucces = False
    self.blConnectInitiated = False
    self.blConnected = False
    self.blCheckedDevices = False
    self.blInitDone = False

  def onHeartbeat(self):
    if (self.blDebug ==  True):
      Domoticz.Log("onHeartbeat called")
    if (self.blDiscoverySocketCreated==False): # If the UDP socket has not yet been created, do it now
      self.createUDPSocket()
    if (self.blDiscoveryRequestSend == True and self.blDiscoverySucces == False):
      self.procesDiscoveryData()
      if (self.blDiscoverySucces == False):
        self.blDiscoveryRequestSend = False     # Resend Discovery frame
    if (self.blDiscoveryRequestSend == False and self.blDiscoverySocketCreated == True): # If the discovery UDP packet has not been send, send it now
      self.sendDiscoveryRequest()
    if (self.blConnectInitiated == False and self.blDiscoverySucces == True):
      self.connect()
    if (self.blConnected==True and self.XMLProcessed==False):
      Domoticz.Log("Requesting XML configuration")
      self.objConnection.Send(Message=createISCPFrame(MESSAGE_RECEIVER_INFORMATION))
    if (self.XMLProcessed==True and self.blCheckedDevices == False):
      self.checkDevices()
    if (self.blCheckedDevices == True and self.blCheckedStates == False):
      self.getInitialStates()
      self.blInitDone = True
      Domoticz.Heartbeat(20)

  def createUDPSocket(self):
    if (self.blDebug ==  True):
      Domoticz.Log("Creating UDP Socket for sending/receiving discovery data")
    self.sockUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.sockUDP.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    self.sockUDP.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    self.sockUDP.settimeout(0.1)
    self.sockUDP.bind(('0.0.0.0', 60128))
    self.blDiscoverySocketCreated = True
    if (self.blDebug ==  True):
      Domoticz.Log("UDP Socket created succesfully")

  def sendDiscoveryRequest(self):
    if (self.blDebug ==  True):
      Domoticz.Log("Sending UDP discovery packet")
    try:
      self.sockUDP.sendto(createISCPFrame(MESSAGE_DISCOVER), ('<broadcast>', 60128))
      self.blDiscoveryRequestSend = True
      if (self.blDebug ==  True):
        Domoticz.Log("UDP Discovery packet send succesfully")
    except:
      if (self.blDebug ==  True):
        Domoticz.Log("UDP Discovery packet could not be send")

  def procesDiscoveryData(self):
    if (self.blDebug ==  True):
      Domoticz.Log("Checking if discovery data has been received")
    data = b''
    blNothingReceived = False
    while blNothingReceived != True: # Repeat this until we have no data left
      try:
        data, addr = self.sockUDP.recvfrom(BUFFER_SIZE)
        strData = str(data,'utf-8')
      except:
        strData = ''
        blNothingReceived = True
      if strData.find('ECN', 0, len(strData)) != -1:
        self.strIPAddress = (addr[0])
        intStartOfNextSegment = strData.find('!', 0, len(strData))
        strType = strData[intStartOfNextSegment+1:intStartOfNextSegment+2]
        if strType == '1':
          Domoticz.Log("Receiver found:")
          self.strModel = strData[intStartOfNextSegment+5:strData.find('/', intStartOfNextSegment+5, len(strData))]
          intStartOfNextSegment=strData.find('/', intStartOfNextSegment, len(strData))+1
          self.strPort = strData[intStartOfNextSegment:strData.find('/', intStartOfNextSegment, len(strData))]
          intStartOfNextSegment=strData.find('/', intStartOfNextSegment, len(strData))+1
          self.strRegion = strData[intStartOfNextSegment:strData.find('/', intStartOfNextSegment, len(strData))]
          intStartOfNextSegment=strData.find('/', intStartOfNextSegment, len(strData))+1
          self.strMAC = strData[intStartOfNextSegment:intStartOfNextSegment+12]
          Domoticz.Log("Type:       AV Receiver or Stereo Receiver")
          Domoticz.Log("Type:       "+self.strModel)
          if self.strRegion == 'DX':
            Domoticz.Log("Region:     North American model")
          if self.strRegion == 'JJ':
            Domoticz.Log("Region:     Japanese model")
          if self.strRegion == 'XX':
            Domoticz.Log("Region:     European or Asian model")
          Domoticz.Log("IP adress:  " + self.strIPAddress)
          Domoticz.Log("eISCP port: " + self.strPort)
          Domoticz.Log("MAC:        " + self.strMAC)
          self.blDiscoverySucces = True
          self.sockUDP.close() # We don't need this anymore

  def checkDevices(self):
    Domoticz.Log("Checking if Devices exist")

    for zone in self.XMLRoot.find('device').find('zonelist'):
      if (int(zone.get('id'))==1) and (int(zone.get('value'))==1):
        # Main zone
        Domoticz.Log('Checking Main zone')
        intMainMaxVolume = int(zone.get('volmax'))
        if (MAINPOWER not in Devices):
          Domoticz.Log("Receiver main power device does not exist, creating device")
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' '+zone.get('name')+" Power", Unit=MAINPOWER, TypeName="Switch",  \
            Image=5).Create()
        else:
          Domoticz.Log("Receiver main power device exists")

        if (MAINSOURCE not in Devices):
          Domoticz.Log("Receiver input selector device does not exist, creating device")
          strSelectorNames = 'Off'
          strSelectorActions = ''
          for selector in self.XMLRoot.find('device').find('selectorlist'):
            strSelectorNames += '|' + selector.get('name')
            strSelectorActions += '|'
          dictOptions = {"LevelActions": strSelectorActions, \
                     "LevelNames": strSelectorNames, \
                     "LevelOffHidden": "true", \
                     "SelectorStyle": "1"}
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' ' + zone.get('name') + " Source", Unit=MAINSOURCE, \
            TypeName="Selector Switch", Switchtype=18, Image=5, \
            Options = dictOptions).Create()
        else:
          Domoticz.Log("Receiver input selector device exists")

        if (MAINLISTENINGMODE not in Devices):
          Domoticz.Log("Receiver listening mode selector device does not exist, creating device")
          strSelectorNames = 'Off'
          strSelectorActions = ''
          for control in self.XMLRoot.find('device').find('controllist'):
            if (control.get('id')[0:3] == 'LMD'):
              strSelectorNames += '|' + control.get('id')[4:]
              strSelectorActions += '|'
          dictOptions = {"LevelActions": strSelectorActions, \
                     "LevelNames": strSelectorNames, \
                     "LevelOffHidden": "true", \
                     "SelectorStyle": "0"}
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' ' + zone.get('name') + " Mode", Unit=MAINLISTENINGMODE, \
            TypeName="Selector Switch", Switchtype=18, Image=5, \
            Options = dictOptions).Create()
        else:
          Domoticz.Log("Receiver listening mode selector device exists")

        if (TUNERPRESETS not in Devices):
          Domoticz.Log("Receiver Tuner preset selector device does not exist, creating device")
          strSelectorNames = 'Off'
          strSelectorActions = ''
          for preset in self.XMLRoot.find('device').find('presetlist'):
            if (preset.get('band') != '0'):
              strSelectorNames += '|' + str(int('0x'+preset.get('id'),16))+' '+preset.get('name')
              strSelectorActions += '|'
          dictOptions = {"LevelActions": strSelectorActions, \
                     "LevelNames": strSelectorNames, \
                     "LevelOffHidden": "true", \
                     "SelectorStyle": "1"}
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            " Tuner", Unit=TUNERPRESETS, \
            TypeName="Selector Switch", Switchtype=18, Image=5, \
            Options=dictOptions).Create()
        else:
          Domoticz.Log("Receiver Tuner preset selector device exists")

        if (MAINVOLUME not in Devices):
          Domoticz.Log("Receiver volume control device does not exist, creating device")
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' ' + zone.get('name') + " Volume", Unit=MAINVOLUME, Type=244, Subtype=73, \
            Switchtype=7, Image=8).Create()
        else:
          Domoticz.Log("Receiver volume control device exists")

      if (int(zone.get('id'))==2) and (int(zone.get('value'))==1):
        # Zone 2
        Domoticz.Log('Checking Zone 2')
        intZone2MaxVolume = int(zone.get('volmax'))
        if (ZONE2POWER not in Devices): 
          Domoticz.Log("Receiver Zone 2 power device does not exist, creating device")
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' '+zone.get('name')+" Power", Unit=ZONE2POWER, TypeName="Switch",  \
            Image=5).Create()
        else:
          Domoticz.Log("Receiver Zone 2 power device exists")

        if (ZONE2SOURCE not in Devices):
          Domoticz.Log("Receiver input selector Zone 2 device does not exist, creating device")
          strSelectorNames = 'Off'
          strSelectorActions = ''
          for selector in self.XMLRoot.find('device').find('selectorlist'):
            strSelectorNames += '|' + selector.get('name')
            strSelectorActions += '|'
          dictOptions = {"LevelActions": strSelectorActions, \
                     "LevelNames": strSelectorNames, \
                     "LevelOffHidden": "true", \
                     "SelectorStyle": "1"}
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' ' + zone.get('name') + " Source", Unit=ZONE2SOURCE, \
            TypeName="Selector Switch", Switchtype=18, Image=5, \
            Options = dictOptions).Create()
        else:
          Domoticz.Log("Receiver input selector Zone 2 device exists")

        if (ZONE2VOLUME not in Devices):
          Domoticz.Log("Receiver Zone 2 volume control device does not exist, creating device")
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' ' + zone.get('name') + " Volume", Unit=ZONE2VOLUME, Type=244, Subtype=73, \
            Switchtype=7, Image=8).Create()
        else:
          Domoticz.Log("Receiver zone 2 volume control device exists")

      if (int(zone.get('id'))==3) and (int(zone.get('value'))==1):
        # Zone 3
        Domoticz.Log('Checking Zone 3')
        intZone3MaxVolume = int(zone.get('volmax'))
        if (ZONE3POWER not in Devices):
          Domoticz.Log("Receiver Zone 3 power device does not exist, creating device")
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' '+zone.get('name')+" Power", Unit=ZONE3POWER, TypeName="Switch",  \
            Image=5).Create()
        else:
          Domoticz.Log("Receiver Zone 3 power device exists")

        if (ZONE3SOURCE not in Devices):
          Domoticz.Log("Receiver input selector Zone 3 device does not exist, creating device")
          strSelectorNames = 'Off'
          strSelectorActions = ''
          for selector in self.XMLRoot.find('device').find('selectorlist'):
            strSelectorNames += '|' + selector.get('name')
            strSelectorActions += '|'
          dictOptions = {"LevelActions": strSelectorActions, \
                     "LevelNames": strSelectorNames, \
                     "LevelOffHidden": "true", \
                     "SelectorStyle": "1"}
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' ' + zone.get('name') + " Source", Unit=ZONE3SOURCE, \
            TypeName="Selector Switch", Switchtype=18, Image=5, \
            Options = dictOptions).Create()
        else:
          Domoticz.Log("Receiver input selector Zone 3 device exists")

        if (ZONE3VOLUME not in Devices):
          Domoticz.Log("Receiver Zone 3 volume control device does not exist, creating device")
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' ' + zone.get('name') + " Volume", Unit=ZONE3VOLUME, Type=244, Subtype=73, \
            Switchtype=7, Image=8).Create()
        else:
          Domoticz.Log("Receiver zone 3 volume control device exists")

      if (int(zone.get('id'))==4) and (int(zone.get('value'))==1):
        # Zone 4
        Domoticz.Log('Checking Zone 4')
        intZone4MaxVolume = int(zone.get('volmax'))
        if (ZONE4POWER not in Devices):
          Domoticz.Log("Receiver Zone 4 power device does not exist, creating device")
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' '+zone.get('name')+" Power", Unit=ZONE4POWER, TypeName="Switch",  \
            Image=5).Create()
        else:
          Domoticz.Log("Receiver Zone 4 power device exists")

        if (ZONE4SOURCE not in Devices):
          Domoticz.Log("Receiver input selector Zone 4 device does not exist, creating device")
          strSelectorNames = 'Off'
          strSelectorActions = ''
          for selector in self.XMLRoot.find('device').find('selectorlist'):
            strSelectorNames += '|' + selector.get('name')
            strSelectorActions += '|'
          dictOptions = {"LevelActions": strSelectorActions, \
                     "LevelNames": strSelectorNames, \
                     "LevelOffHidden": "true", \
                     "SelectorStyle": "1"}
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' ' + zone.get('name') + " Source", Unit=ZONE4SOURCE, \
            TypeName="Selector Switch", Switchtype=18, Image=5, \
            Options = dictOptions).Create()
        else:
          Domoticz.Log("Receiver input selector Zone 4 device exists")

        if (ZONE4VOLUME not in Devices):
          Domoticz.Log("Receiver Zone 4 volume control device does not exist, creating device")
          Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
            ' ' + zone.get('name') + " Volume", Unit=ZONE4VOLUME, Type=244, Subtype=73, \
            Switchtype=7, Image=8).Create()
        else:
          Domoticz.Log("Receiver zone 4 volume control device exists")

    self.blCheckedDevices = True

  def getInitialStates(self):
    for zone in self.XMLRoot.find('device').find('zonelist'):
      if (int(zone.get('id'))==1) and (int(zone.get('value'))==1):
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_POWER+'QSTN'), Delay=1)
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_VOLUME+'QSTN'), Delay=2)
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_SOURCE+'QSTN'), Delay=3)
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_TUNERPRESET+'QSTN'), Delay=4)
      if (int(zone.get('id'))==2) and (int(zone.get('value'))==1):
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_POWER2+'QSTN'), Delay=5)
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_VOLUME2+'QSTN'), Delay=6)
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_SOURCE2+'QSTN'), Delay=7)
      if (int(zone.get('id'))==3) and (int(zone.get('value'))==1):
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_POWER3+'QSTN'), Delay=8)
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_VOLUME3+'QSTN'), Delay=9)
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_SOURCE3+'QSTN'), Delay=10)
      if (int(zone.get('id'))==4) and (int(zone.get('value'))==1):
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_POWER4+'QSTN'), Delay=11)
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_VOLUME4+'QSTN'), Delay=12)
        self.objConnection.Send(Message=createISCPFrame(MESSAGE_SOURCE4+'QSTN'), Delay=13)

    self.blCheckedStates = True
    

  def connect(self):
    if (self.blDebug ==  True):
      Domoticz.Log("Connecting to Receiver")
    self.objConnection = Domoticz.Connection(Name="Onkyo Connection", Transport="TCP/IP", Protocol="NONE", Address=self.strIPAddress, Port=self.strPort)
    self.objConnection.Connect()
    self.blConnectInitiated =  True

  def checkInputBuffer(self):
    intStartOfFrame = self.bInputBuffer.find(b'ISCP')
    if (intStartOfFrame > -1): 
      if (intStartOfFrame > 0):
        if (self.blDebug ==  True):
          Domoticz.Log('We have garbage in the input buffer, getting rid of: '+str(intStartOfFrame)+' bytes.')
        self.bInputBuffer = self.bInputBuffer[intStartOfFrame:]    # Get rid of possible left overs in front of the first complete frame
      if (self.blDebug ==  True):
        Domoticz.Log('Found ISCP frame')
      intHeaderSize = self.bInputBuffer[7] + pow(2,8)*self.bInputBuffer[6] +  pow(2,16) * self.bInputBuffer[5] + pow(2,32)*self.bInputBuffer[4]
      if (self.blDebug ==  True):
        Domoticz.Log('HeaderSize: '+ str(intHeaderSize))
      intDataSize = self.bInputBuffer[11] + pow(2,8)*self.bInputBuffer[10] +  pow(2,16) * self.bInputBuffer[9] + pow(2,32)*self.bInputBuffer[8]
      if (self.blDebug ==  True):
        Domoticz.Log('DataSize: '+ str(intDataSize))
        Domoticz.Log('Have ' + str(len(self.bInputBuffer)) + ' bytes in inputbuffer') 
      if (len(self.bInputBuffer) >= intHeaderSize + intDataSize): 
        return True
      else:
        return False    # We do not have a complete frame yet
    return False

  def processeISCPFrame(self):
    if (self.bInputBuffer[0:4] == b'ISCP'):
      if (self.blDebug ==  True):
        Domoticz.Log('Found ISCP frame')
      intHeaderSize = self.bInputBuffer[7] + pow(2,8)*self.bInputBuffer[6] +  pow(2,16) * self.bInputBuffer[5] + pow(2,32)*self.bInputBuffer[4]
      if (self.blDebug ==  True):
        Domoticz.Log('HeaderSize: '+ str(intHeaderSize))
      intDataSize = self.bInputBuffer[11] + pow(2,8)*self.bInputBuffer[10] +  pow(2,16) * self.bInputBuffer[9] + pow(2,32)*self.bInputBuffer[8]
      if (self.blDebug ==  True):
        Domoticz.Log('DataSize: '+ str(intDataSize))
      intVersion = int(self.bInputBuffer[12])
      if (self.blDebug ==  True):
        Domoticz.Log('Version: ' + str(intVersion))
        Domoticz.Log('Reserved: [' + hex(self.bInputBuffer[13])+']['+ hex(self.bInputBuffer[14])+']['+ hex(self.bInputBuffer[15])+']')
      streISCPData = self.bInputBuffer[16:21].decode(encoding="ascii", errors="ignore")
      if (self.blDebug ==  True):
        Domoticz.Log('eISCP Data : ' + streISCPData)
      streISCPMessage = self.bInputBuffer[21: self.bInputBuffer[21:].find(EOF)+21].decode(encoding="ascii", errors="ignore")
      if (self.blDebug ==  True):
        Domoticz.Log('eISCP Message: ' + streISCPMessage)
      self.bInputBuffer = self.bInputBuffer[16+intDataSize:]  # Remove this frame from the InputBuffer

      if (streISCPData==MESSAGE_POWER):
        #Main Zone Power
        if streISCPMessage=='01':
          #Power On
          UpdateDevice(MAINPOWER, 1, "On")
        if streISCPMessage=='00':
          # Power Off
          UpdateDevice(MAINPOWER, 0, "Off")
      if (streISCPData==MESSAGE_MUTE):
        if streISCPMessage=='01':
          #Mute
          UpdateDevice(MAINVOLUME, 0, "Off")
        if streISCPMessage=='00':
          #Unmute
          UpdateDevice(MAINVOLUME, 1, "On")
      if (streISCPData==MESSAGE_VOLUME):
        if streISCPMessage == 'N/A':
          intVolume = NA
        else:
          intVolume = int(int('0x'+streISCPMessage, 16)*(100/self.intMainMaxVolume))
        if (intVolume != NA):
          Domoticz.Log('Volume: '+str(intVolume))
          UpdateDevice(MAINVOLUME,2,str(intVolume))
      if (streISCPData==MESSAGE_SOURCE):
        if (self.blDebug ==  True):
          Domoticz.Log('Source: '+streISCPMessage)
        for selector in self.XMLRoot.find('device').find('selectorlist'):
          if (selector.get('id').upper() == streISCPMessage.upper()):
            Domoticz.Log('Current Source: '+selector.get('name'))
            setSelectorByName(MAINSOURCE, selector.get('name'))

      if (streISCPData==MESSAGE_POWER2):
        #Zone 2 Power
        if streISCPMessage=='01':
          #Power On
          UpdateDevice(ZONE2POWER, 1, "On")
        if streISCPMessage=='00':
          # Power Off
          UpdateDevice(ZONE2POWER, 0, "Off")
      if (streISCPData==MESSAGE_MUTE2):
        if streISCPMessage=='01':
          #Mute zone 2
          UpdateDevice(ZONE2VOLUME, 0, "Off")
        if streISCPMessage=='00':
          #Unmute zone 2
          UpdateDevice(ZONE2VOLUME, 1, "On")
      if (streISCPData==MESSAGE_VOLUME2):
        if streISCPMessage == 'N/A':
          intVolume = NA
        else:
          intVolume = int(int('0x'+streISCPMessage, 16)*(100/self.intZone2MaxVolume))
        if (intVolume != NA):
          Domoticz.Log('Zone2 volume: '+str(intVolume))
          UpdateDevice(ZONE2VOLUME,2,str(intVolume))
      if (streISCPData==MESSAGE_SOURCE2):
        if (self.blDebug ==  True):
          Domoticz.Log('Zone 2 source: '+streISCPMessage)
        for selector in self.XMLRoot.find('device').find('selectorlist'):
          if (selector.get('id').upper() == streISCPMessage.upper()):
            Domoticz.Log('Zone 2 Current Source: '+selector.get('name'))
            setSelectorByName(ZONE2SOURCE, selector.get('name'))

      if (streISCPData==MESSAGE_POWER3):
        #Zone 3 Power
        if streISCPMessage=='01':
          #Power On
          UpdateDevice(ZONE3POWER, 1, "On")
        if streISCPMessage=='00':
          # Power Off
          UpdateDevice(ZONE3POWER, 0, "Off")
      if (streISCPData==MESSAGE_MUTE3):
        if streISCPMessage=='01':
          #Mute zone 3
          UpdateDevice(ZONE3VOLUME, 0, "Off")
        if streISCPMessage=='00':
          #Unmute zone 3
          UpdateDevice(ZONE3VOLUME, 1, "On")
      if (streISCPData==MESSAGE_VOLUME3):
        if streISCPMessage == 'N/A':
          intVolume = NA
        else:
          intVolume = int(int('0x'+streISCPMessage, 16)*(100/self.intZone3MaxVolume))
        if (intVolume != NA):
          Domoticz.Log('Zone3 volume: '+str(intVolume))
          UpdateDevice(ZONE3VOLUME,2,str(intVolume))
      if (streISCPData==MESSAGE_SOURCE3):
        if (self.blDebug ==  True):
          Domoticz.Log('Zone 3 source: '+streISCPMessage)
        for selector in self.XMLRoot.find('device').find('selectorlist'):
          if (selector.get('id').upper() == streISCPMessage.upper()):
            Domoticz.Log('Zone 3 Current Source: '+selector.get('name'))
            setSelectorByName(ZONE3SOURCE, selector.get('name'))
 
      if (streISCPData==MESSAGE_POWER4):
        #Zone 4 Power
        if streISCPMessage=='01':
          #Power On
          UpdateDevice(ZONE4POWER, 1, "On")
        if streISCPMessage=='00':
          # Power Off
          UpdateDevice(ZONE4POWER, 0, "Off")
      if (streISCPData==MESSAGE_MUTE3):
        if streISCPMessage=='01':
          #Mute zone 4
          UpdateDevice(ZONE4VOLUME, 0, "Off")
        if streISCPMessage=='00':
          #Unmute zone 4
          UpdateDevice(ZONE4VOLUME, 1, "On")
      if (streISCPData==MESSAGE_VOLUME4):
        if streISCPMessage == 'N/A':
          intVolume = NA
        else:
          intVolume = int(int('0x'+streISCPMessage, 16)*(100/self.intZone4MaxVolume))
        if (intVolume != NA):
          Domoticz.Log('Zone4 volume: '+str(intVolume))
          UpdateDevice(ZONE4VOLUME,2,str(intVolume))
      if (streISCPData==MESSAGE_SOURCE4):
        if (self.blDebug ==  True):
          Domoticz.Log('Zone 4 source: '+streISCPMessage)
        for selector in self.XMLRoot.find('device').find('selectorlist'):
          if (selector.get('id').upper() == streISCPMessage.upper()):
            Domoticz.Log('Zone 4 Current Source: '+selector.get('name'))
            setSelectorByName(ZONE4SOURCE, selector.get('name'))

      if (streISCPData==MESSAGE_TUNERPRESET):
        if (self.blDebug ==  True):
          Domoticz.Log('Preset: '+streISCPMessage)
        for preset in self.XMLRoot.find('device').find('presetlist'):
          if (preset.get('id').upper() == streISCPMessage.upper()):
            strPresetName = str(int('0x'+preset.get('id'),16))+' '+preset.get('name')
            setSelectorByName(TUNERPRESETS, strPresetName)

      if (streISCPData==MESSAGE_LISTENINGMODE):
        if (self.blDebug ==  True):
          Domoticz.Log('Listening mode: '+streISCPMessage)
        if (streISCPMessage != 'N/A'):
          blLMDFound = False
          for control in self.XMLRoot.find('device').find('controllist'):
            if (control.get('id')[0:3] == 'LMD'):
              Domoticz.Log('EISCP message: '+ streISCPMessage)
              Domoticz.Log('XML code: '+ control.get('code'))
              if (control.get('code').upper() == streISCPMessage.upper()):
               strListeningModeName = control.get('id')[4:]
               setSelectorByName(MAINLISTENINGMODE, strListeningModeName)
               blLMDFound = True
          if (blLMDFound == False):
            if (setSelectorByCode(MAINLISTENINGMODE, streISCPMessage.upper()) == False):
              addListeningMode(streISCPMessage.upper())
              setSelectorByCode(MAINLISTENINGMODE, streISCPMessage.upper())
  
      if (streISCPData=='!1NRI'):
        # We should now have the XML
        Domoticz.Log('Received XML')
        self.XMLBuffer = streISCPMessage[streISCPMessage.find('<'):streISCPMessage.rfind('>')+1]
        self.XMLRoot = XMLTree.fromstring(self.XMLBuffer)
        self.XMLProcessed=True
        #self.ProcessXML()
    else:
      if (self.blDebug ==  True):
        Domoticz.Log('NON eISCP data found: ' + data)

  def ProcessXML(self):
    Domoticz.Log('Response status: ' + self.XMLRoot.get('status'))
    Domoticz.Log('id             : ' + (self.XMLRoot.find('device').attrib).get('id'))
    Domoticz.Log('brand          : ' + (self.XMLRoot.find('device')).find('brand').text)
    Domoticz.Log('category       : ' + (self.XMLRoot.find('device')).find('category').text)
    Domoticz.Log('brand          : ' + (self.XMLRoot.find('device')).find('brand').text)
    Domoticz.Log('year           : ' + (self.XMLRoot.find('device')).find('year').text)
    Domoticz.Log('model          : ' + (self.XMLRoot.find('device')).find('model').text)
    Domoticz.Log('destination    : ' + (self.XMLRoot.find('device')).find('destination').text)
    Domoticz.Log('modeliconurl   : ' + (self.XMLRoot.find('device')).find('modeliconurl').text)
    Domoticz.Log('friendlyname   : ' + (self.XMLRoot.find('device')).find('friendlyname').text)
    Domoticz.Log('firmwareversion: ' + (self.XMLRoot.find('device')).find('firmwareversion').text)
    Domoticz.Log('zonelist: ' + (self.XMLRoot.find('device').find('zonelist')).get('count'))
    for zone in self.XMLRoot.find('device').find('zonelist'):
      Domoticz.Log('zone id: ' + zone.get('id') + ', value: ' + zone.get('value') + ', name: ' + zone.get('name') + ', volmax: ' + zone.get('volmax'))
    Domoticz.Log('selectorlist: ' + (self.XMLRoot.find('device').find('selectorlist')).get('count'))
    for selector in self.XMLRoot.find('device').find('selectorlist'):
      Domoticz.Log('selector id: ' + selector.get('id') + ', value: ' + selector.get('value') + ', name: ' + selector.get('name'))
    Domoticz.Log('presetlist: ' + (self.XMLRoot.find('device').find('presetlist')).get('count'))
    for preset in self.XMLRoot.find('device').find('presetlist'):
      Domoticz.Log('preset id: ' + preset.get('id') + ', band: ' + preset.get('band') + ', freq: ' + preset.get('freq') + ', name: ' + preset.get('name'))
    for control in self.XMLRoot.find('device').find('controllist'):
      if (control.get('id')[0:3] == 'LMD'):
        Domoticz.Log('control id: ' + control.get('id')[4:] + ', code: ' + control.get('code'))

global _plugin
_plugin = Onkyo()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

    # Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Log( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Log("Onkyo: Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Log("Onkyo: Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Log("Onkyo: Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Log("Onkyo: Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Log("Onkyo: Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Log("Onkyo: Device LastLevel: " + str(Devices[x].LastLevel))
    return

def createISCPFrame(message):
  ISCPFrame = bytes(MESSAGE_HEADER_1+chr(len(message)+1)+MESSAGE_HEADER_2+message+MESSAGE_TRAILER, 'UTF-8')
  return ISCPFrame

def UpdateDevice(Unit, nValue, sValue):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it 
    if (Unit in Devices):
      Domoticz.Log("Update "+str(nValue)+":'"+str(sValue)+"' ("+Devices[Unit].Name+")")
      if (Devices[Unit].nValue != nValue) or (Devices[Unit].sValue != sValue):
        Devices[Unit].Update(nValue, str(sValue))

def setSelectorByName(intId, strName):
  dictOptions = Devices[intId].Options
  listLevelNames = dictOptions['LevelNames'].split('|')
  intLevel = 0
  for strLevelName in listLevelNames:
    if strLevelName == strName:
      Devices[intId].Update(1,str(intLevel))
    intLevel += 10

def setSelectorByCode(intId, strCode):
  Domoticz.Log("Onkyo: setSelectorByCode code: "+strCode)
  dictOptions = Devices[intId].Options
  Domoticz.Log("Onkyo: Fetched Options")
  Domoticz.Log("Onkyo: options: "+dictOptions['LevelNames'])
  listLevelNames = dictOptions['LevelNames'].split('|')
  intLevel = 0
  Domoticz.Log("Onkyo: Starting Loop")
  for strLevelName in listLevelNames:
    Domoticz.Log(strLevelName[1:3])
    if strLevelName[1:3] == strCode:
      Domoticz.Log("Onkyo: found level: +"+str(intLevel))
      Devices[intId].Update(1,str(intLevel))
      return True
    intLevel += 10
  return False

def addListeningMode(strCode):
  nValue = Devices[MAINLISTENINGMODE].nValue
  sValue = Devices[MAINLISTENINGMODE].sValue
  dictOptions = Devices[MAINLISTENINGMODE].Options 
  Domoticz.Log(dictOptions["LevelActions"])
  Domoticz.Log(dictOptions["LevelNames"])
  dictOptions["LevelNames"] = dictOptions["LevelNames"]+'|['+strCode+']'+' New'
  dictOptions["LevelActions"] = dictOptions["LevelActions"]+'|'
  Domoticz.Log(dictOptions["LevelActions"])
  Domoticz.Log(dictOptions["LevelNames"])

  Devices[MAINLISTENINGMODE].Update(nValue = nValue, sValue = sValue, Options = dictOptions) 

#  Domoticz.Device(Name=(self.XMLRoot.find('device')).find('model').text + \
#            ' ' + zone.get('name') + " Mode", Unit=MAINLISTENINGMODE, \
#            TypeName="Selector Switch", Switchtype=18, Image=5, \
#            Options = dictOptions).Create()
