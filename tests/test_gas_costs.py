#! pytest
"""This file contains tests so that there is no regression in the gas costs,
 for example because of a different solidity version.
 The tests are meant to exhibit unexpected increase in gas costs.
 They are not meant to enforce a limit.
 """
import pytest
from texttable import Texttable
from web3 import Web3
from tldeploy.core import deploy_network, deploy_identity, get_chain_id
from tldeploy.identity import deploy_proxied_identity

from .conftest import EXTRA_DATA, EXPIRATION_TIME

trustlines = [
    (0, 1, 100, 150),
    (1, 2, 200, 250),
    (2, 3, 300, 350),
    (3, 4, 400, 450),
    (0, 4, 500, 550),
]  # (A, B, clAB, clBA)


def get_gas_costs(web3, tx_hash):
    tx_receipt = web3.eth.getTransactionReceipt(tx_hash)
    return tx_receipt.gasUsed


def report_gas_costs(table: Texttable, topic: str, gas_cost: int, limit: int) -> None:
    table.add_row([topic, gas_cost])
    assert (
        gas_cost <= limit
    ), "Cost for {} were {} gas and exceeded the limit {}".format(
        topic, gas_cost, limit
    )


@pytest.fixture(scope="session")
def table():
    table = Texttable()
    table.add_row(["Topic", "Gas cost"])
    yield table
    print()
    print(table.draw())


@pytest.fixture(scope="session")
def currency_network_contract(web3):
    return deploy_network(
        web3,
        name="Teuro",
        symbol="TEUR",
        decimals=2,
        fee_divisor=100,
        currency_network_contract_name="TestCurrencyNetwork",
        expiration_time=EXPIRATION_TIME,
    )


@pytest.fixture(scope="session")
def currency_network_contract_with_trustlines(web3, accounts):
    contract = deploy_network(
        web3,
        name="Teuro",
        symbol="TEUR",
        decimals=2,
        fee_divisor=100,
        currency_network_contract_name="TestCurrencyNetwork",
        expiration_time=EXPIRATION_TIME,
    )
    for (A, B, clAB, clBA) in trustlines:
        contract.functions.setAccount(
            accounts[A], accounts[B], clAB, clBA, 0, 0, False, 1, 1
        ).transact()
    return contract


@pytest.fixture(scope="session")
def identity_implementation(deploy_contract, web3):

    identity_implementation = deploy_contract("Identity")
    return identity_implementation


@pytest.fixture(scope="session")
def proxy_factory(deploy_contract, web3):

    proxy_factory = deploy_contract(
        "IdentityProxyFactory", constructor_args=(get_chain_id(web3),)
    )
    return proxy_factory


@pytest.fixture(scope="session")
def signature_of_owner_on_implementation(
    account_keys, identity_implementation, proxy_factory
):
    abi_types = ["bytes1", "bytes1", "address", "address"]
    to_hash = ["0x19", "0x00", proxy_factory.address, identity_implementation.address]
    to_sign = Web3.solidityKeccak(abi_types, to_hash)
    return account_keys[3].sign_msg_hash(to_sign).to_bytes()


def test_cost_transfer_0_mediators(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    tx_hash = contract.functions.transfer(100, 2, [A, B], EXTRA_DATA).transact(
        {"from": A}
    )
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, "0 hop transfer", gas_cost, limit=48000)


def test_cost_transfer_1_mediators(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, C, *rest = accounts
    tx_hash = contract.functions.transfer(50, 4, [A, B, C], EXTRA_DATA).transact(
        {"from": A}
    )
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, "1 hop transfer", gas_cost, limit=65000)


def test_cost_transfer_2_mediators(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, C, D, *rest = accounts
    tx_hash = contract.functions.transfer(50, 6, [A, B, C, D], EXTRA_DATA).transact(
        {"from": A}
    )
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, "2 hop transfer", gas_cost, limit=83500)


def test_cost_transfer_3_mediators(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, C, D, E, *rest = accounts
    tx_hash = contract.functions.transfer(50, 8, [A, B, C, D, E], EXTRA_DATA).transact(
        {"from": A}
    )
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, "3 hop transfer", gas_cost, limit=101_500)


def test_cost_first_trustline_request(web3, currency_network_contract, accounts, table):
    contract = currency_network_contract
    A, B, *rest = accounts
    tx_hash = contract.functions.updateCreditlimits(B, 150, 150).transact({"from": A})
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, "First Trustline Update Request", gas_cost, limit=78500)


def test_cost_second_trustline_request(
    web3, currency_network_contract, accounts, table
):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.updateCreditlimits(B, 149, 149).transact({"from": A})
    tx_hash = contract.functions.updateCreditlimits(B, 150, 150).transact({"from": A})
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, "Second Trustline Update Request", gas_cost, limit=47000)


def test_cost_first_trustline(web3, currency_network_contract, accounts, table):
    contract = currency_network_contract
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 0
    contract.functions.updateCreditlimits(B, 150, 150).transact({"from": A})
    tx_hash = contract.functions.updateCreditlimits(A, 150, 150).transact({"from": B})
    assert contract.functions.creditline(A, B).call() == 150
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, "First Trustline", gas_cost, limit=315_000)


def test_cost_update_trustline(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 100
    contract.functions.updateCreditlimits(B, 150, 150).transact({"from": A})
    tx_hash = contract.functions.updateCreditlimits(A, 150, 150).transact({"from": B})
    assert contract.functions.creditline(A, B).call() == 150
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, "Update Trustline", gas_cost, limit=56000)


def test_cost_update_reduce_need_no_accept_trustline(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 100
    tx_hash = contract.functions.updateCreditlimits(B, 99, 150).transact({"from": A})
    assert contract.functions.creditline(A, B).call() == 99
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, "Reduce Trustline", gas_cost, limit=66000)


def test_cost_close_trustline(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    contract.functions.transfer(1, 0, [A, B], EXTRA_DATA).transact({"from": A})
    assert contract.functions.balance(A, B).call() == 0

    tx_hash = contract.functions.closeTrustline(B).transact({"from": A})
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, "Close Trustline", gas_cost, limit=55000)


def test_deploy_identity(web3, accounts, table):
    A, *rest = accounts

    block_number_before = web3.eth.blockNumber

    deploy_identity(web3, A)

    block_number_after = web3.eth.blockNumber

    gas_cost = 0
    for block_number in range(block_number_after, block_number_before, -1):
        gas_cost += web3.eth.getBlock(block_number).gasUsed

    report_gas_costs(table, "Deploy Identity", gas_cost, limit=1_400_000)


def test_deploy_proxied_identity(
    web3,
    table,
    proxy_factory,
    identity_implementation,
    signature_of_owner_on_implementation,
):
    block_number_before = web3.eth.blockNumber

    deploy_proxied_identity(
        web3,
        proxy_factory.address,
        identity_implementation.address,
        signature_of_owner_on_implementation,
    )

    block_number_after = web3.eth.blockNumber

    gas_cost = 0
    for block_number in range(block_number_after, block_number_before, -1):
        gas_cost += web3.eth.getBlock(block_number).gasUsed

    report_gas_costs(table, "Deploy Proxied Identity", gas_cost, limit=310_000)
