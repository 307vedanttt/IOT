import os
import urllib.request

base = "https://raw.githubusercontent.com/arduino/Arduino/master/build/windows/dist/drivers/FTDI%20USB%20Drivers"
target_dir = r"D:\Projects\IOT\ftdi_drivers"
os.makedirs(os.path.join(target_dir, "amd64"), exist_ok=True)

files = [
    "ftdibus.cat",
    "ftdibus.inf",
    "ftdiport.cat",
    "ftdiport.inf",
    "amd64/ftbusui.dll",
    "amd64/ftcserco.dll",
    "amd64/ftd2xx.lib",
    "amd64/ftd2xx64.dll",
    "amd64/ftdibus.sys",
    "amd64/ftlang.dll",
    "amd64/ftser2k.sys",
    "amd64/ftserui2.dll"
]

for f in files:
    url = f"{base}/{f}"
    dest = os.path.join(target_dir, f.replace("/", "\\"))
    print(f"Downloading {f}...")
    urllib.request.urlretrieve(url, dest)

print("All FTDI driver files downloaded successfully.")

