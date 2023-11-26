# OCPP server with ability to send commands by mqtt
# for home automation projects

import asyncio
import logging
from datetime import datetime
from aiomqtt import Client, MqttError
import sys, os
from dotenv import load_dotenv
import signal



# check dependancies
try:
    import websockets
except ModuleNotFoundError:
    print("This example relies on the 'websockets' package.")
    print("Please install it by running: ")
    print()
    print(" $ pip install websockets")
    import sys

    sys.exit(1)

from ocpp.routing import on
from ocpp.v16 import ChargePoint as cp
from ocpp.v16 import call
from ocpp.v16 import call_result
from ocpp.v16.enums import AuthorizationStatus, Action, RegistrationStatus, RemoteStartStopStatus, ChargingProfilePurposeType, ChargingProfileKindType, ChargingRateUnitType, MessageTrigger

logging.basicConfig(level=logging.INFO)

load_dotenv(verbose=True)
MQTT_USERNAME=os.getenv('MQTT_USERNAME')
MQTT_PASSWORD=os.getenv('MQTT_PASSWORD')
LISTEN_ADDR=os.getenv('LISTEN_ADDR') # 0.0.0.0 for localhost
TAG_ID=os.getenv('TAG_ID')

class ChargePoint(cp):
    @on(Action.BootNotification)
    def on_boot_notification(
        self, charge_point_vendor: str, charge_point_model: str, **kwargs
    ):
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted,
        )
    
    @on(Action.Heartbeat)
    async def on_heartbeat(self):
        #print("--- Got a Heartbeat! :: " + str(self.heartbeat))
        #if self.heartbeat == 3:
        #    self.remote_start_transaction()
        await self.client.publish("/ocpp/heartbeat", payload="ON")
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        )
    
    @on(Action.StatusNotification)
    async def on_status_notification(
        self, connector_id: int, error_code: str, status: str, **kwargs
    ):
        print("--- Got Status Notification")
        await self.client.publish("/ocpp/notification_status", payload=status)
        await self.client.publish("/ocpp/notification_error", payload=error_code)
        return call_result.StatusNotificationPayload()

    @on(Action.Authorize)
    def on_authorize(self, id_tag: str):
        print("--- Got Authorization")
        """TODO: ! padaryti autentifikacijos patikrinima"""
        return call_result.AuthorizePayload(
            id_tag_info={'status': AuthorizationStatus.accepted}
        )
    # this is home implementation with no authorization needs, 
    # so I put constant transaction number 112 
    @on(Action.StartTransaction)
    def on_start_transaction(self, connector_id: int, id_tag: str, meter_start: int, timestamp: str, **kwargs):
        print('--- Started transaction in CP')
        return call_result.StartTransactionPayload(
            transaction_id=112,         
            id_tag_info={'status': AuthorizationStatus.accepted}
        )
    
    @on(Action.StopTransaction)
    def on_stop_transaction(self,  **kwargs):
        print('--- Stopped transaction in CP')
        for k,v in kwargs.items():
            print(k, v)
        self.unlock_connector() # unlock connector when transaction stopped
        return call_result.StopTransactionPayload(
            id_tag_info={'status': AuthorizationStatus.accepted}
        )

    @on(Action.MeterValues)
    def on_meter_values(self, **kwargs):
        print('--- Stopped transaction in CP')
        for k,v in kwargs.items():
            print(k, v)
        return call_result.MeterValuesPayload()


    async def trigger_message(self):
        request = call.TriggerMessagePayload(
            requested_message=MessageTrigger.statusNotification,
            connector_id=1
        )
        print('---trigger message')
        response = await self.call(request)
        print("--- TRIGGER:" + str(response))
        
    async def remote_start_transaction(self):
        request = call.RemoteStartTransactionPayload(
            id_tag=TAG_ID         
        )
        response = await self.call(request)
        if response.status == RemoteStartStopStatus.accepted:
            print("------- Transaction Started!!!")

    async def remote_stop_transaction(self):
        request = call.RemoteStopTransactionPayload(
            transaction_id=112
        )
        response = await self.call(request)
        if response.status == RemoteStartStopStatus.accepted:
            print("Stopping transaction")

    async def set_charging_profile(self, amps, **kwargs):
        print('set_charging_profile')
        return await self.call(call.SetChargingProfilePayload(
            connector_id=1,
            cs_charging_profiles={
                'charging_profile_id': int(amps),
                'stack_level': 0,
                'charging_profile_purpose': ChargingProfilePurposeType.txprofile,
                'charging_profile_kind': ChargingProfileKindType.absolute,
                'charging_schedule': {
                    'charging_rate_unit': ChargingRateUnitType.amps,
                    'charging_schedule_period': [{
                        'start_period': 0,
                        'limit': float(amps),
                    }]
                },
                'transaction_id': 112
            }
        ))

    # request to change CP configuration
    async def change_configuration(self, key:str, value:str):
        request = call.ChangeConfigurationPayload(key=key, value=value)
        response = await self.call(request)
        print("set configuration: key- {}, value- {}, status- {}".format(key, value, response.status))
        #await self.client.publish("/ocpp/configuration", payload=str(response.status)

    # reda CP configuration
    async def get_configuration(self):
        request = call.GetConfigurationPayload()
        response = await self.call(request)
        print("--- CONFIGURATION:")
        print(response)
        for setting in response.configuration_key:
            print(f"{setting['key']}: {setting['value']}")

    # MQTT implementation
    async def mqtt_listen(self):
        print("start mqtt")
        async with Client(hostname="10.0.20.240",port=1883,username=MQTT_USERNAME,password=MQTT_PASSWORD) as self.client:
            async with self.client.messages() as messages:
                await self.client.subscribe("/ocpp/cmd/#")
                async for message in messages:
                    msg = str(message.payload.decode("utf-8")).split()
                    print("MQTT msg: ")
                    print(msg)
                    if msg[0] == "start":
                        await self.remote_start_transaction()
                    if msg[0] == "stop":
                        await self.remote_stop_transaction()
                    if msg[0] == "trigger":
                        await self.trigger_message()
                    if msg[0] == "profile":
                        await self.set_charging_profile(int(msg[1]))
                    if msg[0] == "unlock":
                        await self.unlock_connector()
                    if msg[0] == "exit":
                        sys.exit(0)
                    if msg[0] == "configuration":
                        await self.get_configuration()
                    if msg[0] == "change_configuration":
                        await self.change_configuration(msg[1], msg[2])
                    if msg[0] == "meter_values":
                        await self.meter_values()


async def on_connect(websocket, path):
    """For every new charge point that connects, create a ChargePoint
    instance and start listening for messages.
    """
    try:
        requested_protocols = websocket.request_headers["Sec-WebSocket-Protocol"]
    except KeyError:
        logging.error("Client hasn't requested any Subprotocol. Closing Connection")
        return await websocket.close()
    if websocket.subprotocol:
        logging.info("Protocols Matched: %s", websocket.subprotocol)
    else:
        # In the websockets lib if no subprotocols are supported by the
        # client and the server, it proceeds without a subprotocol,
        # so we have to manually close the connection.
        logging.warning(
            "Protocols Mismatched | Expected Subprotocols: %s,"
            " but client supports  %s | Closing connection",
            websocket.available_subprotocols,
            requested_protocols,
        )
        return await websocket.close()

    charge_point_id = path.strip("/")
    cp1 = ChargePoint(charge_point_id, websocket)
    cp1.heartbeat = 0

    
    #await cp.start()
    print("!!! cp.start() completed")
    await asyncio.gather( cp1.start(), cp1.mqtt_listen())
    
    """
    try:
        await cp.start()
    except websockets.exceptions.ConnectionClosed:
        print("--- websockets connection closed")
    """

class SignalHandler:
    shutdown_requested = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.request_shutdown)
        signal.signal(signal.SIGTERM, self.request_shutdown)

    def request_shutdown(self, *args):
        print('Request to shutdown received, stopping')
        self.shutdown_requested = True
        sys.exit(0)

    def can_run(self):
        return not self.shutdown_requested



async def main():

    server = await websockets.serve(
        on_connect, LISTEN_ADDR, 9003, subprotocols=["ocpp1.6"], ping_timeout = None
    )
    logging.info("Server Started listening to new connections...")
    await server.wait_closed()

signal_handler = SignalHandler()   

if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
    set_event_loop_policy(WindowsSelectorEventLoopPolicy())


if __name__ == "__main__":
    # asyncio.run() is used when running this example with Python >= 3.7v
    asyncio.run(main())
