#! pytest

import time

import pytest

from tldeploy.core import deploy_network, deploy_exchange, deploy
from tldeploy.exchange import Order
from tldeploy.signing import priv_to_pubkey


trustlines = [(0, 1, 100, 150),
              (1, 2, 200, 250),
              (2, 3, 300, 350),
              (3, 4, 400, 450),
              (0, 4, 500, 550)
              ]  # (A, B, clAB, clBA)


NULL_ADDRESS = '0x0000000000000000000000000000000000000000'


@pytest.fixture(scope='session')
def exchange_contract(web3):
    return deploy_exchange(web3)


@pytest.fixture(scope='session')
def token_contract(web3, accounts):
    A, B, C, *rest = accounts
    contract = deploy("DummyToken", web3, 'DummyToken', 'DT', 18, 10000000)
    contract.functions.setBalance(A, 10000).transact()
    contract.functions.setBalance(B, 10000).transact()
    contract.functions.setBalance(C, 10000).transact()
    return contract


@pytest.fixture(scope='session')
def currency_network_contract_with_trustlines(web3, exchange_contract, accounts):
    contract = deploy_network(web3, name="TestCoin", symbol="T", decimals=6, fee_divisor=0)
    for (A, B, clAB, clBA) in trustlines:
        contract.functions.setAccount(accounts[A], accounts[B], clAB, clBA, 0, 0, 0, 0, 0, 0).transact()
    contract.functions.addAuthorizedAddress(exchange_contract.address).transact()
    return contract


def test_order_hash(exchange_contract, token_contract, currency_network_contract_with_trustlines, accounts):
    maker_address, taker_address, *rest = accounts

    order = Order(exchange_contract.address,
                  maker_address,
                  NULL_ADDRESS,
                  token_contract.address,
                  currency_network_contract_with_trustlines.address,
                  NULL_ADDRESS,
                  100,
                  50,
                  0,
                  0,
                  1234,
                  1234
                  )

    assert order.hash() == exchange_contract.functions.getOrderHash(
        [order.maker_address,
         order.taker_address,
         order.maker_token,
         order.taker_token,
         order.fee_recipient],
        [order.maker_token_amount,
         order.taker_token_amount,
         order.maker_fee,
         order.taker_fee,
         order.expiration_timestamp_in_sec,
         order.salt]
    ).call()


def test_order_signature(
        exchange_contract,
        token_contract,
        currency_network_contract_with_trustlines,
        accounts,
        account_keys,
):
    maker_address, taker_address, *rest = accounts
    maker_key = account_keys[0]

    order = Order(exchange_contract.address,
                  maker_address,
                  NULL_ADDRESS,
                  token_contract.address,
                  currency_network_contract_with_trustlines.address,
                  NULL_ADDRESS,
                  100,
                  50,
                  0,
                  0,
                  1234,
                  1234
                  )

    v, r, s = order.sign(maker_key.to_bytes())

    assert exchange_contract.functions.isValidSignature(maker_address, order.hash().hex(), v, r, s).call()


def test_exchange(exchange_contract,
                  token_contract,
                  currency_network_contract_with_trustlines,
                  accounts,
                  account_keys):
    maker_address, mediator_address, taker_address, *rest = accounts
    maker_key = account_keys[0]

    assert token_contract.functions.balanceOf(maker_address).call() == 10000
    assert token_contract.functions.balanceOf(taker_address).call() == 10000
    assert currency_network_contract_with_trustlines.functions.balance(maker_address, mediator_address).call() == 0
    assert currency_network_contract_with_trustlines.functions.balance(mediator_address, taker_address).call() == 0

    token_contract.functions.approve(exchange_contract.address, 100).transact({'from': maker_address})

    order = Order(exchange_contract.address,
                  maker_address,
                  NULL_ADDRESS,
                  token_contract.address,
                  currency_network_contract_with_trustlines.address,
                  NULL_ADDRESS,
                  100,
                  50,
                  0,
                  0,
                  int(time.time()+60*60*24),
                  1234
                  )

    assert priv_to_pubkey(maker_key.to_bytes()) == maker_address

    v, r, s = order.sign(maker_key.to_bytes())

    exchange_contract.functions.fillOrderTrustlines(
          [order.maker_address, order.taker_address, order.maker_token, order.taker_token, order.fee_recipient],
          [order.maker_token_amount, order.taker_token_amount, order.maker_fee,
           order.taker_fee, order.expiration_timestamp_in_sec, order.salt],
          50,
          [],
          [mediator_address, maker_address],
          v,
          r,
          s).transact({'from': taker_address})

    assert token_contract.functions.balanceOf(maker_address).call() == 9900
    assert token_contract.functions.balanceOf(taker_address).call() == 10100
    assert currency_network_contract_with_trustlines.functions.balance(maker_address, mediator_address).call() == 50
    assert currency_network_contract_with_trustlines.functions.balance(taker_address, mediator_address).call() == -50
