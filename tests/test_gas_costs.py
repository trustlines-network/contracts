#! pytest
"""This file contains tests so that there is o regression in the gas costs,
 for example because of a different solidity version"""
import pytest
from texttable import Texttable
from tldeploy.core import deploy_network

trustlines = [(0, 1, 100, 150),
              (1, 2, 200, 250),
              (2, 3, 300, 350),
              (3, 4, 400, 450),
              (0, 4, 500, 550)
              ]  # (A, B, clAB, clBA)


def get_gas_costs(web3, tx_hash):
    tx_receipt = web3.eth.getTransactionReceipt(tx_hash)
    return tx_receipt.gasUsed


def report_gas_costs(table: Texttable, topic: str, gas_cost: int, limit: int) -> None:
    table.add_row([topic, gas_cost])
    assert gas_cost <= limit, 'Cost for {} were {} gas and exceeded the limit {}'.format(topic, gas_cost, limit)


@pytest.fixture(scope='session')
def table():
    table = Texttable()
    table.add_row(['Topic', 'Gas cost'])
    yield table
    print()
    print(table.draw())


@pytest.fixture()
def currency_network_contract(web3):
    return deploy_network(web3, name="Teuro", symbol="TEUR", decimals=2, fee_divisor=100)


@pytest.fixture()
def currency_network_contract_with_trustlines(currency_network_contract, accounts):
    contract = currency_network_contract
    for (A, B, clAB, clBA) in trustlines:
        contract.functions.setAccount(accounts[A], accounts[B], clAB, clBA, 0, 0, 0, 0, 1, 1).transact()
    return contract


def test_cost_transfer_0_mediators(web3, currency_network_contract_with_trustlines, accounts, table):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    tx_hash = contract.functions.transfer(B, 100, 2, [accounts[1]]).transact({'from': A})
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, '0 hop transfer', gas_cost, limit=45000)


def test_cost_transfer_1_mediators(web3, currency_network_contract_with_trustlines, accounts, table):
    contract = currency_network_contract_with_trustlines
    A, B, C, *rest = accounts
    tx_hash = contract.functions.transfer(C, 50, 4, [B, C]).transact({'from': A})
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, '1 hop transfer', gas_cost, limit=61000)


def test_cost_transfer_2_mediators(web3, currency_network_contract_with_trustlines, accounts, table):
    contract = currency_network_contract_with_trustlines
    A, B, C, D, *rest = accounts
    tx_hash = contract.functions.transfer(D, 50, 6, [B, C, D]).transact({'from': A})
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, '2 hop transfer', gas_cost, limit=78000)


def test_cost_transfer_3_mediators(web3, currency_network_contract_with_trustlines, accounts, table):
    contract = currency_network_contract_with_trustlines
    A, B, C, D, E, *rest = accounts
    tx_hash = contract.functions.transfer(E, 50, 8, [B, C, D, E]).transact({'from': A})
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, '3 hop transfer', gas_cost, limit=94000)


def test_cost_first_trustline_request(web3, currency_network_contract, accounts, table):
    contract = currency_network_contract
    A, B, *rest = accounts
    tx_hash = contract.functions.updateCreditlimits(B, 150, 150).transact({"from": A})
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, 'First Trustline Update Request', gas_cost, limit=77000)


def test_cost_second_trustline_request(web3, currency_network_contract, accounts, table):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.updateCreditlimits(B, 149, 149).transact({"from": A})
    tx_hash = contract.functions.updateCreditlimits(B, 150, 150).transact({"from": A})
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, 'Second Trustline Update Request', gas_cost, limit=47000)


def test_cost_first_trustline(web3, currency_network_contract, accounts, table):
    contract = currency_network_contract
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 0
    contract.functions.updateCreditlimits(B, 150, 150).transact({"from": A})
    tx_hash = contract.functions.updateCreditlimits(A, 150, 150).transact({"from": B})
    assert contract.functions.creditline(A, B).call() == 150
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, 'First Trustline', gas_cost, limit=315000)


def test_cost_update_trustline(web3, currency_network_contract_with_trustlines, accounts, table):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 100
    contract.functions.updateCreditlimits(B, 150, 150).transact({"from": A})
    tx_hash = contract.functions.updateCreditlimits(A, 150, 150).transact({"from": B})
    assert contract.functions.creditline(A, B).call() == 150
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, 'Update Trustline', gas_cost, limit=56000)


def test_cost_update_reduce_need_no_accept_trustline(web3, currency_network_contract_with_trustlines, accounts, table):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 100
    tx_hash = contract.functions.updateCreditlimits(B, 99, 150).transact({"from": A})
    assert contract.functions.creditline(A, B).call() == 99
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, 'Reduce Trustline', gas_cost, limit=66000)


def test_cost_close_trustline(web3, currency_network_contract_with_trustlines, accounts, table):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    contract.functions.transfer(B, 1, 0, [B]).transact({"from": A})
    assert contract.functions.balance(A, B).call() == 0

    tx_hash = contract.functions.closeTrustline(B).transact({"from": A})
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(table, 'Close Trustline', gas_cost, limit=55000)
