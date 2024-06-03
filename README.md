<h1 align="center" id="title">Wiresense.py</h1>

![wiresense.py](https://socialify.git.ci/Wiresense/wiresense.py/image?font=Inter&forks=1&issues=1&language=1&owner=1&pattern=Solid&pulls=1&stargazers=1&theme=Auto)

<p align="center">
    <img src="https://img.shields.io/badge/Made%20with%20Love%E2%9D%A4%EF%B8%8F-black?style=for-the-badge" alt="made with love">
    <img src="https://img.shields.io/badge/async%20io%20-FFD147?style=for-the-badge&logo=python&logoColor=%233670A0" alt="asyncio">
    <img src="https://img.shields.io/github/actions/workflow/status/Wiresense/wiresense.py/publish.yml?style=for-the-badge" alt="build status">
    <img src="https://img.shields.io/pypi/v/wiresense?style=for-the-badge" alt="pypi version">
    <img src="https://img.shields.io/pypi/dm/wiresense?style=for-the-badge" alt="pypi downloads">
</p>

Client libary for Wiresense

## 🛠️Features

- Send data to the wiresense frontend
- Works with almost every sensor
- Automaticly saved data into csv files

## 📖Usage

Install the libary with pip:

```bash
pip install wiresense
```

Import the libary and configure it

```python
from wiresense import Wiresense

await Wiresense.config({
    "port": 8080
})
```

Setup a new sensor (group)

```python
def readSensorData():
    # Replace with you actual sensor reading logic
    return {
        "Pressure": random.randint(0, 10),
        "Humidity": random.randint(0, 10),
        "Temperature": random.randint(0, 10),
    }

sensor_1 = Wiresense('Fake-BME280', readSensorData, './data/sensor1_data.csv')
```

Execute a sensor (Send to frontend and save to file)

```python
await sensor_1.execute()
```

Please note that Wiresense is an asynchronous library and requires execution within an asyncio event loop. Make sure to run the main function using asyncio.run() or within an existing asyncio application.


## 📜License

[MIT](https://choosealicense.com/licenses/mit/)

## ✍️Authors

- [@saladrian](https://www.github.com/saladrian)