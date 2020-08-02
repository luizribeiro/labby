from time import sleep as sleep_orig
from dataclasses import dataclass
from unittest import TestCase
from unittest.mock import Mock, patch

from labctl.config import Config
from labctl.experiment import (
    BaseInputParameters,
    BaseOutputData,
    Experiment,
)
from labctl.experiment.runner import ExperimentRunner
from labctl.hw.core import auto_discover_drivers
from labctl.tests.utils import fake_serial_port


@dataclass(frozen=True)
class OutputData(BaseOutputData):
    voltage: float


@dataclass(frozen=True)
class InputParameters(BaseInputParameters):
    pass


class TestExperiment(Experiment[InputParameters, OutputData]):
    SAMPLING_RATE_IN_HZ: float = 2.0
    DURATION_IN_SECONDS: float = 1.0

    def start(self) -> None:
        power_supply = self.get_power_supply("zup-6-132")
        power_supply.open()

    def measure(self) -> OutputData:
        power_supply = self.get_power_supply("zup-6-132")
        actual_voltage = power_supply.get_actual_voltage()
        return OutputData(voltage=actual_voltage)

    def stop(self) -> None:
        power_supply = self.get_power_supply("zup-6-132")
        power_supply.close()


LABCTL_CONFIG_YAML = """
---
devices:
  - name: "zup-6-132"
    type: power_supply
    driver: labctl.hw.tdklambda.power_supply.ZUP
    args:
      port: "/dev/ttyUSB0"
      baudrate: 9600
      address: 1
"""


class ExperimentRunnerTest(TestCase):
    def setUp(self) -> None:
        auto_discover_drivers()

    def test_output_data_type_metadata(self) -> None:
        input_parameters = InputParameters()
        experiment = TestExperiment("test_experiment", input_parameters)
        output_data_type = experiment.get_output_data_type()
        self.assertEquals(output_data_type.get_column_names(), ["voltage"])

    @fake_serial_port
    def test_run_single_experiment(self, serial_port_mock: Mock) -> None:
        serial_port_mock.readline.return_value = b"AV2.0\r\n"
        config = Config(LABCTL_CONFIG_YAML)

        input_parameters = InputParameters()
        experiment = TestExperiment("test_experiment", input_parameters)

        runner = ExperimentRunner(config, experiment)

        with patch("time.sleep", side_effect=sleep_orig):
            # TODO make these tests less dependent on time and less hacky
            runner.run_experiment()

        dataframe = runner.dataframe
        self.assertEquals(dataframe.columns.to_list(), ["seconds", "voltage"])
        self.assertEquals(dataframe["voltage"].to_list(), [2.0, 2.0])

        with self.assertRaises(AssertionError):
            # cannot run the same experiment again with the same ExperimentRunner
            runner.run_experiment()
