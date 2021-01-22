#! pytest
from deploy_tools import deploy_compiled_contract
import pytest

from tldeploy.core import deploy_network, NetworkSettings

from tests.conftest import EXPIRATION_TIME

ADDRESS_0 = "0x0000000000000000000000000000000000000000"
NO_ONBOARDER = "0x0000000000000000000000000000000000000001"


trustlines = [
    (0, 1, 100, 150),
    (1, 2, 200, 250),
    (2, 3, 300, 350),
    (3, 4, 400, 450),
    (0, 4, 500, 550),
]  # (A, B, clAB, clBA)

NETWORK_SETTING = NetworkSettings(name="TestCoin", symbol="T")


def deploy_test_network(web3, network_setting, **kwargs):
    return deploy_network(
        web3,
        network_setting,
        currency_network_contract_name="TestCurrencyNetwork",
        **kwargs,
    )


def deploy_ownable_network(web3, network_setting, **kwargs):
    return deploy_network(
        web3,
        network_setting,
        currency_network_contract_name="CurrencyNetworkOwnable",
        **kwargs,
    )


@pytest.fixture(scope="session")
def currency_network_contract(web3):
    return deploy_test_network(web3, NETWORK_SETTING)


@pytest.fixture(scope="session")
def currency_network_adapter(currency_network_contract, make_currency_network_adapter):
    return make_currency_network_adapter(currency_network_contract)


@pytest.fixture(scope="session")
def currency_network_contract_with_trustlines(
    web3, accounts, make_currency_network_adapter
):
    contract = deploy_test_network(
        web3, NetworkSettings(expiration_time=EXPIRATION_TIME)
    )
    for (A, B, clAB, clBA) in trustlines:
        make_currency_network_adapter(contract).set_account(
            accounts[A], accounts[B], creditline_given=clAB, creditline_received=clBA
        )
    return contract


@pytest.fixture(scope="session")
def currency_network_adapter_with_trustlines(
    currency_network_contract_with_trustlines, make_currency_network_adapter
):
    return make_currency_network_adapter(currency_network_contract_with_trustlines)


@pytest.fixture(scope="session")
def currency_network_contract_custom_interest(web3):
    network_settings = NetworkSettings(
        custom_interests=True, expiration_time=EXPIRATION_TIME
    )
    return deploy_test_network(web3, network_settings)


@pytest.fixture(scope="session")
def currency_network_adapter_custom_interest(
    currency_network_contract_custom_interest, make_currency_network_adapter
):
    return make_currency_network_adapter(currency_network_contract_custom_interest)


@pytest.fixture(scope="session")
def currency_network_contract_with_fees(web3):
    setting = NetworkSettings(fee_divisor=100, custom_interests=True)
    return deploy_test_network(web3, setting)


@pytest.fixture(scope="session")
def currency_network_adapter_with_fees(
    currency_network_contract_with_fees, make_currency_network_adapter
):
    return make_currency_network_adapter(currency_network_contract_with_fees)


@pytest.fixture(scope="session")
def upgradeable_implementation(deploy_contract):
    return deploy_contract(contract_identifier="TestUpgradeable")


@pytest.fixture(scope="session")
def upgraded_implementation(deploy_contract):
    return deploy_contract(contract_identifier="TestUpgraded")


@pytest.fixture(scope="session")
def proxy_beacon(owner_key, contract_assets, web3, upgradeable_implementation):
    return deploy_compiled_contract(
        abi=contract_assets["ProxyBeacon"]["abi"],
        bytecode=contract_assets["ProxyBeacon"]["bytecode"],
        constructor_args=(upgradeable_implementation.address,),
        web3=web3,
        private_key=owner_key,
    )


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def owner_key(account_keys):
    return account_keys[0]


@pytest.fixture(scope="session")
def not_owner(accounts, owner):
    not_owner = accounts[1]
    assert not_owner != owner
    return not_owner


@pytest.fixture(scope="session")
def not_owner_key(account_keys):
    return account_keys[1]


@pytest.fixture(scope="session")
def owned_currency_network(web3, owner):
    settings = NetworkSettings(custom_interests=True)
    return deploy_ownable_network(web3, settings, transaction_options={"from": owner})


@pytest.fixture(scope="session")
def beacon_with_currency_network(
    web3, owned_currency_network, contract_assets, owner_key
):
    return deploy_compiled_contract(
        abi=contract_assets["ProxyBeacon"]["abi"],
        bytecode=contract_assets["ProxyBeacon"]["bytecode"],
        constructor_args=(owned_currency_network.address,),
        web3=web3,
        private_key=owner_key,
    )
