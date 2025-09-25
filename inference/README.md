# MobileRL Evaluation Framework

This directory contains the [AgentRL](https://github.com/THUDM/AgentRL-Env)-based evaluation framework for MobileRL
that integrates the [Android Lab](https://github.com/THUDM/Android-Lab) test set
and [Android World](https://github.com/google-research/android_world) test set.


We provide two usage modes:  
- Local testing for easy debugging and modification  
- Docker-based deployment using AgentRL for convenient deployment  

It should be noted that the results reported in this paper were obtained using SGLang with Docker-based deployment. Given that online training environments are subject to a variety of factors that may influence performance—such as deployment configurations, inference engines, and image compression rates and methods—variations of 1–2% are not uncommon. Furthermore, as the online evaluation requires the execution of multiple correct steps to yield the final SR score, such fluctuations are to be expected. To ensure reliability, the MobileRL reported results were averaged over three independent runs. For researchers who intend to train their own models using our framework, it is essential to ensure that training and inference remain strictly consistent, as any divergence may compromise the comparability of results.


## Local Test

### Getting Started

For Python deployment, you may follow these steps:

```shell
# from inference/
mkdir -p ../third_party
cd ../third_party

# If you want to eval android world, you should install android_env and android_world by: 
git clone https://github.com/google-deepmind/android_env.git
cd android_env
git checkout 1c4e8a92da09ac1886e24f09fa8baa6dddabc4c6
git apply --check ../../inference/extra/android_env.patch
git apply ../../inference/extra/android_env.patch
cd ..
git clone https://github.com/google-research/android_world.git
cd android_world
git checkout cac18549cd8cbb3094f827939765cebf5877fd1e
git apply --check ../../inference/extra/android_world.patch
git apply ../../inference/extra/android_world.patch
cd ../..

# create and activate a new virtualenv, make sure python>=3.11
python3 -m venv venv
source venv/bin/activate

# install all dependencies
python -m pip install --upgrade pip
python -m pip install -e ./third_party/android_env -r ./third_party/android_world/requirements.txt -e ./third_party/android_world -r ./requirements.txt -e .
python -m pip install -r ./inference/requirements.txt
pip install -U protobuf
```

### Install Local ADB & Redis

We need to install adb on the local machine. After successful installation, record your adb path, e.g., /path/android-sdk/platform-tools/adb

If you want to run tests in parallel, you need to start the Redis service first. You can quickly start it with the following command:

```
docker run --name myredis -d -p 6379:6379 redis:7
```

### Modify Your Config

At this step, you need to modify your config yaml file according to your testing requirements. We provide examples at scripts/configs.

Run following command to start testing: 

```
python -m scripts.eval_local -n test_name -c path/to/config.yaml -d android_world/android_lab
``` 


## AgentRL-based Test

### Getting Started

We provide a one-command demo to quickly spin-up the stack with Docker Compose.
To run the demo, please make sure that you have KVM enabled on your host,
and that no ADB server or Android Emulator instances are running on the host machine.

First, generate a new ADB key pair if you don't have one:

```shell
adb keygen ./adbkey
```

Then start the Docker Compose stack:

```shell
docker compose up
```

This command will download or build the necessary Docker images and start the following services in Docker:

- AgentRL Controller
- ADB server
- Port Allocator
- Android Lab task worker (x1, increase as needed)
- Android World task worker (x1, increase as needed)
- Redis server (for container allocation)

See the detailed hardware requirements and how to configure concurrency below.



### Deployment Details

The inference framework is based on [AgentRL](https://github.com/THUDM/AgentRL-Env),
which consists of a controller and multiple task workers.

#### AgentRL Controller

You may run the AgentRL controller in a docker container or directly on the host machine.

To run the controller directly on the host machine, please refer to the [AgentRL README](https://github.com/THUDM/AgentRL-Env/blob/main/README.md#prebuilt-binaries).

To run the controller in a docker container:

```shell
docker run -d --name agentrl-controller --network host jingbh/agentrl-controller:latest controller
```

#### Task Workers

The AgentRL task worker can be run directly as a Python mobile or as Docker containers.

For Docker deployment, refer to the `docker-compose.yml` file for a detailed specification.

For direct Python deployment, you may follow these steps:

```shell
# from inference/
mkdir -p ../third_party
cd ../third_party

# clone android_env
git clone https://github.com/google-deepmind/android_env.git
cd android_env
git checkout 1c4e8a92da09ac1886e24f09fa8baa6dddabc4c6
git apply --check ../../inference/extra/android_env.patch
git apply ../../inference/extra/android_env.patch
cd ..

# clone android_world
git clone https://github.com/google-research/android_world.git
cd android_world
git checkout cac18549cd8cbb3094f827939765cebf5877fd1e
git apply --check ../../inference/extra/android_world.patch
git apply ../../inference/extra/android_world.patch
cd ../..

# create and activate a new virtualenv
python3 -m venv venv
source venv/bin/activate

# install all dependencies
python -m pip install --upgrade pip
python -m pip install -e ./third_party/android_env -r ./third_party/android_world/requirements.txt -e ./third_party/android_world -r ./requirements.txt -e .
python -m pip install -r ./inference/requirements.txt
pip install -U protobuf

# run the task worker
cd inference
python -m agentrl.worker --help
```

#### Configuring Task Workers

The full configuration file for Android Lab and Android World task workers can be found in `configs`.

If you are running locally as Python scripts, you may directly modify the config files and pass the file name as an argument:

```shell
python -m agentrl.worker --config configs/android_lab.yaml --controller http://localhost:5020/api android_lab-test
```

If you are running the task worker as Docker containers, it is possible to override config entries with environment variables.

The environment variables should be named as the configuration keys in uppercase, replacing dots, dashes with underscores.

For example, to override the `name` parameter of the `android_lab-test` task,
you can set the environment variable `ANDROID_LAB_TEST_PARAMETERS_NAME` to the desired value.

There's also a display of this feature in `android_world` task in the provided `docker-compose.yml` file.

#### Begin Evaluation

After task workers are successfully set up, you can begin evaluation with different types of models. 
We provide examples of two invocation methods: using **sglang** to run a model locally, and using the **OpenAI format** for calling closed-source models.
Please note that you may need to install the correct version of **sglang** to execute this code.

```shell
# for sglang
python -m scripts.eval_deployment \
  "android_lab-test" \
  -m /path/to/your/model \
  -c http://localhost:5020/api \
  -r 0,10 \
  -o RUN_OUTPUT_DIR \
  --store-name SAVE_NAME \
  --inference-backend sgl 

# for openai format
# Since different closed-source models require different parameters, 
# we only provide an example with the model name and message.
export OPENAI_API_KEY=sk-xxx
python -m scripts.eval_deployment \
  "android_lab-test" \
  -m /path/to/your/model \
  -c http://localhost:5020/api \
  -r 0,10 \
  -o RUN_OUTPUT_DIR \
  --store-name SAVE_NAME \
  --inference-backend openai 
```

## Special Note for Android World

As SMS tasks in Android World require the Android Emulator to have host network,
it requires a separate ADB server and port allocator to containerize.

Make sure no ADB server and Android Emulator instances are running on the host machine,
then run the docker compose specification to try it out.

The `adbkey` and `adbkey.pub` key pair should be shared between the ADB server and the Android World task workers.
You may obtain them from your local `~/.android/` directory or generate new ones with `adb keygen`.

## Special Note for AndroidLab

AndroidLab uses GLM-4 as judger for query tasks. Please configure your API key in `configs/android_lab.yaml`.

```yaml
judge_args:
    api_key: 'Your API Key'
```