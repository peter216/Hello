#!/usr/bin/env python3
from typing import (
    List,
    Dict,
    Any,
    Optional,
    Tuple,
    Callable,
    TypeVar,
    Union,
    Iterator,
    Type,
)
import sys
from infoblox_netmri.client import InfobloxNetMRI
import pandas as pd
from datetime import datetime, timedelta
from getpass import getpass
import os
import csv
import argparse
import asyncio
import logging
from functools import wraps, partial

if os.name == "nt":
    python_execuable = "/usr/bin/env python"
else:
    python_execuable = "/usr/bin/env python3"


# Type aliases
DeviceType = Any  # Replace with actual type from InfobloxNetMRI if available
BrokerType = Any  # Replace with actual type from InfobloxNetMRI if available
T = TypeVar("T")  # For generic return types
error_flag: bool = False

class RetryError(Exception):
    pass

# ANSI COLORS
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
RESET = "\033[0m"

def async_retry(
    retries: int = 3,
    delay: float = 1,
    backoff: float = 2,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Retry decorator for async functions with type hints
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == retries:
                        raise RetryError(f"Failed after {retries} retries: {str(e)}")
                    logger = args[0].logger if hasattr(args[0], "logger") else None
                    if logger:
                        logger.warning(
                            f"Attempt {attempt + 1}/{retries} failed: {str(e)}. "
                            f"Retrying in {current_delay} seconds..."
                        )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator

class Netmri_Device_Getter:
    netmri_user: Optional[str] = os.getenv("NETMRI_USER")
    netmri_password: Optional[str] = os.getenv("NETMRI_PASSWORD")
    def __init__(
        self,
        params: Dict[str, Any],
        fields: List[str],
        limit: int,
        license_check_limit: int,
        servers: List[str],
        licensed_all: bool,
        logger: logging.Logger,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: int = 1,
        outputfile: str = None,
    ) -> None:
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        self.retry_delay: int = retry_delay
        self.fields: List[str] = fields
        self.search_params: Dict[str, Any] = params
        self.limit: int = limit
        self.license_check_limit: int = license_check_limit
        self.licensed_field: Optional[str] = None
        self.servers: List[str] = servers
        self.licensed_all: bool = licensed_all
        self.devices: List[DeviceType] = []
        self.logger: logging.Logger = logger
        self.clientdict: Dict[str, InfobloxNetMRI] = {}
        self.license_data: List[Dict] = {}
        self.device_total: int = 0
        # Initialize credentials if not set
        if not isinstance(self.netmri_user, str):
            self.netmri_user = input("Enter the username for NetMRI: ")
        if not isinstance(self.netmri_password, str):
            self.netmri_password = getpass(
                f"Enter the password for {self.netmri_user}: "
            )
        if outputfile:
            self.outputfile = outputfile
        else:
            self.outputfile = None
        # Initialize clients
        for server in self.servers:
            client = InfobloxNetMRI(
                host=server, username=self.netmri_user, password=self.netmri_password
            )
            self.clientdict[server] = client
    @async_retry(
        retries=3, delay=1, backoff=2, exceptions=(Exception, asyncio.TimeoutError)
    )
    async def _make_api_call(self, func: Callable[..., T], **kwargs: Any) -> T:
        """Wrapper for API calls with timeout"""
        return await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, partial(func, **kwargs)),
            timeout=self.timeout,
        )
    async def get_netmri_devices(self, server: str) -> Optional[List[DeviceType]]:
        try:
            client: InfobloxNetMRI = self.clientdict[server]
            broker: BrokerType = client.get_broker("Device")
            self.search_params.update(limit=self.limit)
            self.logger.info(f"Search params: {self.search_params}")
            try:
                data_attributes: Dict[str, int] = await self._make_api_call(
                    client.api_request,
                    method_name="devices/find",
                    params=self.search_params,
                )
                total_matches = int(data_attributes["total"])
                self.logger.info(f"Found {total_matches} matching devices on {server}")
                server_devices: List[DeviceType] = []
                start = 1
                while len(server_devices) < total_matches:
                    self.logger.info(
                        f"{server}: Searching for devices at count {start}"
                    )
                    these_devices: List[DeviceType] = await self._make_api_call(
                        broker.find, start=start, **self.search_params
                    )
                    self.logger.info(
                        f"{server}: Retrieved {len(these_devices)} devices"
                    )
                    server_devices.extend(these_devices)
                    this_license_data: List[Dict] = await self.get_license_data(
                        server, these_devices
                    )
                    devcount: int = self.write_devices_to_csv(
                        self.outputfile,
                        these_devices,
                        this_license_data,
                        server,
                        self.licensed_all,
                    )
                    self.device_total += devcount
                    self.logger.info(f"{server}: Found so far: {len(server_devices)}")
                    start += self.limit
                    these_devices = []
                self.devices.extend(server_devices)
                return server_devices
            except RetryError as e:
                self.logger.error(f"All retries failed for {server}: {str(e)}")
                print(f"{RED}All retries failed for {server}: {str(e)}{RESET}")
                error_flag = True
                return None
        except Exception as e:
            self.logger.error(f"Unhandled error querying {server}: {e.__class__}: {e}")
            print(f"{RED}Unhandled error querying {server}: {e.__class__}: {e}{RESET}")
            error_flag = True
            return None
    async def get_license_data(
        self, server: str, devices: List[DeviceType]
    ) -> Dict[int, bool]:
        try:
            self.logger.info(f"{server}: Getting license data")
            client: InfobloxNetMRI = self.clientdict[server]
            broker: BrokerType = client.get_broker("DeviceSetting")
            deviceids: List[Tuple[int, str]] = [d.DeviceID for d in devices]
            license_data: Dict[int, bool] = {}
            try:
                start = 1
                while start <= len(deviceids):
                    self.logger.info(
                        f"{server}: Calling API for license data, start={start}"
                    )
                    device_settings: List[Any] = await self._make_api_call(
                        broker.find,
                        DeviceID=deviceids,
                        start=start,
                        limit=self.license_check_limit,
                    )
                    this_license_data = {
                        d.DeviceID: d.DeviceLicensedInd for d in device_settings
                    }
                    license_data.update(this_license_data)
                    start += self.license_check_limit
                self.logger.info(f"{server}: License data retrieved")
            except RetryError as e:
                self.logger.error(f"Failed to get license data: {str(e)}")
                raise
        except Exception as e:
            self.logger.error(
                f"Unhandled error getting license data from {server}: {e.__class__}: {e}"
            )
            print(
                f"{RED}Unhandled error getting license data from {server}: {e.__class__}: {e}{RESET}"
            )
            error_flag = True
            return None
        else:
            return license_data
    def write_devices_to_csv(
        self,
        outputfile: Optional[str],
        devices: List[DeviceType],
        license_data: List[Dict],
        server: str,
        licensed_all: bool,
    ) -> int:
        df = pd.DataFrame([d.__dict__ for d in devices], columns=self.fields)
        df["licensed"] = df["DeviceID"].map(license_data)
        df["server"] = server
        if not licensed_all:
            df = df[df["licensed"]]
        if not outputfile:
            print(df.to_csv(index=False, header=False))
        else:
            outputfile_not_exists: bool = not os.path.exists(outputfile)
            with open(outputfile, "a") as OFH:
                df.to_csv(
                    outputfile,
                    index=False,
                    header=outputfile_not_exists,
                )
                OFH.flush()
        device_count: int = len(df)
        return device_count

async def main() -> None:
    try:
        now: datetime = datetime.now()
        default_fields: List[str] = [
            "DeviceName",
            "DeviceIPDotted",
            "DeviceType",
            "DeviceVendor",
            "DeviceModel",
            "DeviceVersion",
            "DeviceTimestamp",
            "DeviceSysDescr",
            "custom_device_tower",
            "custom_marsha",
            "DeviceID",
        ]
        network_devices_only_params: Dict[str, str] = {
            "op_DeviceType": "rlike",
            "val_c_DeviceType": "Switch|Router",
        }
        search_params: Dict[str, str] = {
            "device_name": "DeviceName",
            "device_ip": "DeviceIPDotted",
            "vendor": "DeviceVendor",
            "model": "DeviceModel",
            "version": "DeviceVersion",
            "sys_descr": "DeviceSysDescr",
            "tower": "custom_device_tower",
            "marsha": "custom_marsha",
            "device_id": "DeviceID",
        }
        params: Dict[str, Any] = {}
        parser: argparse.ArgumentParser = argparse.ArgumentParser()
        parser.add_argument(
            "--network_devices_only",
            action="store_true",
            default=False,
            help="Search for network devices only (default true)",
        )
        parser.add_argument(
            "--device_name",
            help="Device name(s) to search for (regex)",
            required=False,
            type=str,
        )
        parser.add_argument(
            "--device_ip",
            help="Device IP(s) to search for (regex)",
            required=False,
            type=str,
        )
        parser.add_argument(
            "--vendor",
            help="Device vendor(s) to search for (regex)",
            required=False,
            type=str,
        )
        parser.add_argument(
            "--model",
            help="Device model(s) to search for (regex)",
            required=False,
            type=str,
        )
        parser.add_argument(
            "--version",
            help="Device version(s) to search for (regex)",
            required=False,
            type=str,
        )
        parser.add_argument(
            "--sys_descr",
            help="Device system description(s) to search for (regex)",
            required=False,
            type=str,
        )
        parser.add_argument(
            "--tower",
            help="Device tower(s) to search for (regex)",
            required=False,
            type=str,
        )
        parser.add_argument(
            "--marsha",
            help="Device marsha(s) to search for (regex)",
            required=False,
            type=str,
        )
        parser.add_argument(
            "--device_id",
            help="Device ID(s) to search for (regex)",
            required=False,
            type=str,
        )
        parser.add_argument(
            "--licensed_all",
            action="store_true",
            required=False,
            default=False,
            help="Set this flag to search for all devices regardless of license status",
        )
        parser.add_argument(
            "-f",
            "--fields",
            help="Fields to include in the CSV output",
            required=False,
            default=",".join(default_fields),
            type=str,
        )
        parser.add_argument(
            "-l",
            "--limit",
            help="Limit the number of devices to search with each query",
            type=int,
            default=500,
        )
        parser.add_argument(
            "--license_check_limit",
            help="Limit the number of devices to check for license per query",
            type=int,
            default=50,
        )
        parser.add_argument(
            "-o",
            "--outputfile",
            help="File to write the CSV output to",
            required=False,
            type=str,
            default="",
        )
        parser.add_argument(
            "-s",
            "--servers",
            help="NetMRI servers to use",
            required=False,
            default="netmrioc1.marriott.com,netmrioc2.marriott.com",
            type=str,
        )
        parser.add_argument(
            "-v",
            "--verbose",
            help="Enable verbose logger",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "--timeout",
            help="Timeout in seconds for API calls (default 30)",
            type=int,
            default=30,
        )
        parser.add_argument(
            "--max-retries",
            help="Maximum number of retries for failed requests (default 3)",
            type=int,
            default=3,
        )
        parser.add_argument(
            "--retry-delay",
            help="Initial delay between retries in seconds (default 1)",
            type=int,
            default=1,
        )
        args: argparse.Namespace = parser.parse_args()
        if args.network_devices_only:
            params.update(network_devices_only_params)
        fields: List[str] = args.fields.split(",") if args.fields else []
        limit: int = args.limit
        license_check_limit: int = args.license_check_limit
        servers: List[str] = args.servers.split(",")
        verbose: bool = args.verbose
        outputfile: str = args.outputfile
        # Update search parameters based on command line arguments
        for search_param, search_field in search_params.items():
            this_field: Optional[str] = getattr(args, search_param)
            if this_field:
                params.update(
                    {
                        f"op_{search_field}": "rlike",
                        f"val_c_{search_field}": this_field,
                        # f"val_c_{search_field}": "(?i)" + this_field,
                    }
                )
        # Configure logging
        loglevel: int = logging.DEBUG if verbose else logging.INFO
        logger: logging.Logger = logging.getLogger(__name__)
        logger.setLevel(loglevel)
        formatter: logging.Formatter = logging.Formatter(
            "%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d:%H:%M:%S",
        )
        handler: logging.FileHandler = logging.FileHandler("search_netmri.log")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.info(f"Starting script")
        # Initialize device getter
        getter: Netmri_Device_Getter = Netmri_Device_Getter(
            params,
            fields,
            limit,
            license_check_limit,
            servers,
            logger=logger,
            timeout=args.timeout,
            max_retries=args.max_retries,
            retry_delay=args.retry_delay,
            outputfile=args.outputfile,
            licensed_all=args.licensed_all,
        )
        logger.info(f"Search params: {getter.search_params}")
        logger.info(f"Fields: {getter.fields}")
        logger.info(f"Limit: {getter.limit}")
        logger.info(f"License check limit: {getter.license_check_limit}")
        print(f"{CYAN}Searching NetMRI for devices on {servers}{RESET}\n")
        if not outputfile:
            csvw = csv.writer(sys.stdout)
            csvw.writerow(getter.fields)
        # Create tasks for parallel execution
        tasks1: List[asyncio.Task[Any]] = []
        for server in servers:
            logger.info(f"Searching NetMRI for devices on {server}")
            tasks1.append(asyncio.create_task(search_server(getter, server)))
        # Wait for all searches to complete
        await asyncio.gather(*tasks1)
        now2: datetime = datetime.now()
        execution_time: timedelta = now2 - now
        if error_flag:
            msg: str = f"Script completed with errors in {execution_time}."
            logger.error(msg)
            print(f"{RED}{msg}{RESET}")
        else:
            msg: str = f"{getter.device_total} devices found in {execution_time}."
            logger.info(msg)
            print(f"{GREEN}{msg}{RESET}")
            if outputfile:
                logger.info("Output in {outputfile}")
                print(f"{GREEN}Output in {outputfile}{RESET}")
        logger.info(f"Script completed.")
    except Exception as e:
        logger.error(f"Unhandled error: {e.__class__}: {e}")
        print(f"{RED}Unhandled error: {e.__class__}: {e}{RESET}")
        error_flag = True

async def search_server(device_getter: Netmri_Device_Getter, server: str) -> None:
    await device_getter.get_netmri_devices(server)

if __name__ == "__main__":
    asyncio.run(main())
