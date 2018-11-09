#! pytest

import pytest
from web3.exceptions import BadFunctionCallOutput
from tldeploy.core import deploy_network
import eth_tester.exceptions

trustlines = [
    (0, 1, 100, 150),
    (1, 2, 200, 250),
    (2, 3, 300, 350),
    (3, 4, 400, 450),
    (0, 4, 500, 550),
]  # (A, B, clAB, clBA)


@pytest.fixture()
def currency_network_contract(web3):
    return deploy_network(web3, name="TestCoin", symbol="T", decimals=6, fee_divisor=0, default_interest_rate=0,
                          custom_interests=False)


@pytest.fixture()
def currency_network_contract_with_trustlines(currency_network_contract, accounts):
    contract = currency_network_contract
    for (A, B, clAB, clBA) in trustlines:
        contract.functions.setAccount(
            accounts[A], accounts[B], clAB, clBA, 0, 0, 0, 0, 0, 0
        ).transact()
    return contract


@pytest.fixture()
def currency_network_contract_custom_interest(web3):
    return deploy_network(web3, name='TestCoin', symbol='T', decimals=6, fee_divisor=0,
                          default_interest_rate=0, custom_interests=True, prevent_mediator_interests=False)


def test_meta_name(currency_network_contract):
    assert currency_network_contract.functions.name().call() == "TestCoin"


def test_meta_symbol(currency_network_contract):
    assert currency_network_contract.functions.symbol().call() == "T"


def test_meta_decimal(currency_network_contract):
    assert currency_network_contract.functions.decimals().call() == 6


def test_users(currency_network_contract_with_trustlines, accounts):
    A, B, C, D, E, *rest = accounts
    assert set(currency_network_contract_with_trustlines.functions.getUsers().call()) == {
        A,
        B,
        C,
        D,
        E,
    }


def test_friends(currency_network_contract_with_trustlines, accounts):
    A, B, C, D, E, *rest = accounts
    assert set(currency_network_contract_with_trustlines.functions.getFriends(A).call()) == {B, E}


def test_set_get_Account(currency_network_contract_custom_interest, accounts):
    contract = currency_network_contract_custom_interest
    contract.functions.setAccount(
        accounts[0], accounts[1], 10, 20, 2, 3, 100, 200, 0, 4
    ).transact()
    assert contract.functions.getAccount(accounts[0], accounts[1]).call() == [
        10,
        20,
        2,
        3,
        100,
        200,
        0,
        4,
    ]
    assert contract.functions.getAccount(accounts[1], accounts[0]).call() == [
        20,
        10,
        3,
        2,
        200,
        100,
        0,
        -4,
    ]
    contract.functions.setAccount(
        accounts[1], accounts[0], 10, 20, 2, 3, 100, 200, 0, 4
    ).transact()
    assert contract.functions.getAccount(accounts[1], accounts[0]).call() == [
        10,
        20,
        2,
        3,
        100,
        200,
        0,
        4,
    ]
    assert contract.functions.getAccount(accounts[0], accounts[1]).call() == [
        20,
        10,
        3,
        2,
        200,
        100,
        0,
        -4,
    ]


def test_creditlines(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    for (A, B, clAB, clBA) in trustlines:
        assert contract.functions.creditline(accounts[A], accounts[B]).call() == clAB
        assert contract.functions.creditline(accounts[B], accounts[A]).call() == clBA
        assert contract.functions.balance(accounts[A], accounts[B]).call() == 0


def test_set_get_Account_default_interests(currency_network_contract, accounts):
    contract = currency_network_contract
    contract.functions.setAccountDefaultInterests(accounts[0], accounts[1], 10, 20, 100, 200, 0, 4).transact()
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)
    assert contract.functions.getAccount(accounts[0], accounts[1]).call() == [10, 20, 0, 0, 100, 200, 0, 4]
    assert contract.functions.getAccount(accounts[1], accounts[0]).call() == [20, 10, 0, 0, 200, 100, 0, -4]
    contract.transact().setAccountDefaultInterests(accounts[1], accounts[0], 10, 20, 100, 200, 0, 4)
    assert contract.functions.getAccount(accounts[1], accounts[0]).call() == [10, 20, 0, 0, 100, 200, 0, 4]
    assert contract.functions.getAccount(accounts[0], accounts[1]).call() == [20, 10, 0, 0, 200, 100, 0, -4]


def test_balance(currency_network_contract, accounts):
    contract = currency_network_contract
    contract.functions.setAccount(
        accounts[0], accounts[1], 10, 20, 0, 0, 100, 200, 0, 4
    ).transact()
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 4
    assert contract.functions.balance(accounts[1], accounts[0]).call() == -4


def test_transfer_0_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transfer(
        accounts[1], 110, 0, [accounts[1]]
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -110


def test_transfer_0_mediators_fail_not_enough_credit(
    currency_network_contract_with_trustlines, accounts
):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(
            accounts[1], 151, 0, [accounts[1]]
        ).transact({"from": accounts[0]})


def test_transfer_0_mediators_fail_wrong_path(
    currency_network_contract_with_trustlines, accounts
):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(
            accounts[1], 110, 0, [accounts[2]]
        ).transact({"from": accounts[0]})
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(
            accounts[2], 1, 0, [accounts[1]]
        ).transact({"from": accounts[0]})


def test_transfer_1_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transfer(
        accounts[2], 110, 0, [accounts[1], accounts[2]]
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -110
    assert contract.functions.balance(accounts[2], accounts[1]).call() == 110


def test_transfer_1_mediators_not_enough_credit(
    currency_network_contract_with_trustlines, accounts
):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(
            accounts[2], 151, 0, [accounts[1], accounts[2]]
        ).transact({"from": accounts[0]})


def test_transfer_1_mediators_not_enough_wrong_path(
    currency_network_contract_with_trustlines, accounts
):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(
            accounts[2], 110, 0, [accounts[1], accounts[3]]
        ).transact({"from": accounts[0]})


def test_transfer_3_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transfer(
        accounts[4], 110, 0, [accounts[1], accounts[2], accounts[3], accounts[4]]
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -110
    assert contract.functions.balance(accounts[1], accounts[2]).call() == -110
    assert contract.functions.balance(accounts[2], accounts[3]).call() == -110
    assert contract.functions.balance(accounts[4], accounts[3]).call() == 110


def test_transfer_payback(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transfer(
        accounts[4], 110, 0, [accounts[1], accounts[2], accounts[3], accounts[4]]
    ).transact({"from": accounts[0]})
    contract.functions.transfer(
        accounts[0], 110, 0, [accounts[3], accounts[2], accounts[1], accounts[0]]
    ).transact({"from": accounts[4]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0
    assert contract.functions.balance(accounts[1], accounts[2]).call() == 0
    assert contract.functions.balance(accounts[2], accounts[3]).call() == 0
    assert contract.functions.balance(accounts[4], accounts[3]).call() == 0


def test_send_back(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0
    contract.functions.transfer(
        accounts[1], 120, 0, [accounts[1]]
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[1], accounts[0]).call() == 120
    contract.functions.transfer(
        accounts[0], 120, 0, [accounts[0]]
    ).transact({"from": accounts[1]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0


def test_send_more(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0
    contract.functions.transfer(
        accounts[1], 120, 0, [accounts[1]]
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[1], accounts[0]).call() == 120
    contract.functions.transfer(
        accounts[0], 200, 0, [accounts[0]]
    ).transact({"from": accounts[1]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 80


def test_update_without_accept_trustline(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 50, 100).transact({"from": A})
    assert contract.functions.creditline(A, B).call() == 0
    assert contract.functions.creditline(B, A).call() == 0
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()
        == []
    )
    assert (
        contract.events.TrustlineUpdateRequest.createFilter(
            fromBlock=0
        ).get_all_entries()[0]["args"]["_creditlineGiven"]
        == 50
    )


def test_update_with_accept_trustline(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 50, 100).transact({"from": A})
    contract.functions.updateTrustline(A, 100, 50).transact({"from": B})
    assert contract.functions.creditline(A, B).call() == 50
    assert contract.functions.creditline(B, A).call() == 100
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0][
            "args"
        ]["_creditor"]
        == A
    )
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0][
            "args"
        ]["_creditlineGiven"]
        == 50
    )


def test_update_with_accept_different_trustline(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 50, 100).transact({"from": A})
    contract.functions.updateTrustline(A, 100, 49).transact({"from": B})
    # this was changed so it will accept the lower common ground
    assert contract.functions.creditline(A, B).call() == 49
    assert contract.functions.creditline(B, A).call() == 100
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0][
            "args"
        ]["_creditor"]
        == A
    )
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0][
            "args"
        ]["_creditlineGiven"]
        == 49
    )


def test_update_with_accept_2nd_trustline(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 50, 100).transact({"from": A})
    contract.functions.updateTrustline(B, 50, 99).transact({"from": A})
    contract.functions.updateTrustline(A, 99, 50).transact({"from": B})
    assert contract.functions.creditline(A, B).call() == 50
    assert contract.functions.creditline(B, A).call() == 99
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0][
            "args"
        ]["_creditor"]
        == A
    )
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0][
            "args"
        ]["_creditlineGiven"]
        == 50
    )


def test_cannot_accept_old_trustline(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 50, 100).transact({"from": A})
    contract.functions.updateTrustline(B, 50, 99).transact({"from": A})
    contract.functions.updateTrustline(A, 100, 50).transact({"from": B})
    assert contract.functions.creditline(A, B).call() == 0
    assert contract.functions.creditline(B, A).call() == 0
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()
        == []
    )


def test_update_reduce_need_no_accept_trustline(
    currency_network_contract_with_trustlines, accounts
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 100
    assert contract.functions.creditline(B, A).call() == 150
    contract.functions.updateTrustline(B, 99, 150).transact({"from": A})
    assert contract.functions.creditline(A, B).call() == 99
    assert contract.functions.creditline(B, A).call() == 150
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0][
            "args"
        ]["_creditlineGiven"]
        == 99
    )


def test_update_without_accept_trustline_interests(currency_network_contract_custom_interest, accounts):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 50, 100, 1, 0).transact({"from": A})

    assert contract.call().interestRate(A, B) == 0
    assert contract.call().interestRate(B, A) == 0
    assert contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries() == []
    assert contract.events.TrustlineUpdateRequest.createFilter(fromBlock=0).get_all_entries()[0]['args'][
               '_interestRateGiven'] == 1


def test_update_with_accept_trustline_interests(currency_network_contract_custom_interest, accounts):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 1, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 50, 0, 1)

    assert contract.call().interestRate(A, B) == 1
    assert contract.call().interestRate(B, A) == 0
    assert contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0]['args']['_creditor'] == A
    assert contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0]['args'][
               '_interestRateGiven'] == 1


def test_update_with_accept_different_trustline_interests(currency_network_contract_custom_interest, accounts):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 1, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 50, 0, 2)
    assert contract.call().interestRate(A, B) == 0
    assert contract.call().interestRate(B, A) == 0
    assert contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries() == []


def test_update_with_accept_2nd_trustline_interests(currency_network_contract_custom_interest, accounts):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 2, 0)
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 1, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 50, 0, 1)
    assert contract.call().interestRate(A, B) == 1
    assert contract.call().interestRate(B, A) == 0
    assert contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0]['args']['_creditor'] == A
    assert contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0]['args'][
               '_interestRateGiven'] == 1


def test_cannot_accept_old_trustline_interests(currency_network_contract_custom_interest, accounts):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 2, 0)
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 1, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 50, 0, 2)
    assert contract.call().interestRate(A, B) == 0
    assert contract.call().interestRate(B, A) == 0
    assert contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries() == []


def test_update_trustline_with_custom_while_forbidden(currency_network_contract, accounts):
    '''Verifies that if the network uses default interests of 0, no custom interests can be put'''
    contract = currency_network_contract

    A, B, *rest = accounts
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.transact({"from": A}).updateTrustline(B, 50, 100, 2, 1)


def test_update_trustline_with_custom_while_forbidden_lowering_interests(currency_network_contract, accounts):
    '''Verifies that if the network uses default interests of 0, no custom interests can be put'''
    contract = currency_network_contract
    contract.transact().init('TestCoin', 'T', 6, 0, 5, False, False)

    A, B, *rest = accounts
    contract.transact().setAccountDefaultInterests(A, B, 200, 200, 0, 0, 0, 0)

    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.transact({"from": A}).updateTrustline(B, 50, 100, 1, 1)


def test_update_trustline_lowering_interest_given(currency_network_contract, accounts):
    '''Verifies that one can update a trustline by lowering interests rate given without agreement of debtor'''
    contract = currency_network_contract
    contract.transact().init('TestCoin', 'T', 6, 0, 0, True, False)

    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 100, 100, 0, 2)
    contract.transact({"from": B}).updateTrustline(A, 100, 100, 1, 0)

    assert contract.call().creditline(A, B) == 100
    assert contract.call().interestRate(B, A) == 1


def test_update_trustline_lowering_interest_received(currency_network_contract, accounts):
    '''Verifies that one can update a trustline by lowering interests rate given without agreement of debtor'''
    contract = currency_network_contract
    contract.transact().init('TestCoin', 'T', 6, 0, 0, True, False)

    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 100, 100, 2, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 100, 0, 1)

    assert contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries() == []


def test_setting_trustline_with_negative_interests_with_custom_interests(currency_network_contract_with_trustlines,
                                                                         accounts):
    '''Verifies we cannot use negative interests if the flag for custom is set'''

    contract = currency_network_contract_with_trustlines
    contract.transact().init('TestCoin', 'T', 6, 0, 0, True, False)

    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.transact().setAccount(accounts[0], accounts[1], 2000000000, 2000000000, -1000, -1000, 0, 0,
                                       1442509455, 100000000)
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    A, B, *rest = accounts
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.transact({"from": A}).updateTrustline(B, 100, 100, -2, 0)


def test_spendable(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.functions.spendableTo(A, B).call() == 150
    assert contract.functions.spendableTo(B, A).call() == 100
    contract.functions.transfer(B, 40, 0, [B]).transact({"from": A})
    assert contract.functions.spendableTo(A, B).call() == 110
    assert contract.functions.spendableTo(B, A).call() == 140


def test_balance_of(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    A, B, C, D, E, *rest = accounts
    assert contract.functions.balanceOf(A).call() == 700
    contract.functions.transfer(B, 40, 0, [B]).transact({"from": A})
    assert contract.functions.balanceOf(A).call() == 660
    contract.functions.transfer(C, 20, 0, [E, D, C]).transact({"from": A})
    assert contract.functions.balanceOf(A).call() == 640


def test_total_supply(currency_network_contract_with_trustlines):
    assert currency_network_contract_with_trustlines.functions.totalSupply().call() == 3250


def test_balance_event(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    contract.functions.transfer(B, 110, 0, [B]).transact({"from": A})
    events = contract.events.BalanceUpdate.createFilter(fromBlock=0).get_all_entries()
    assert len(events) == 1
    args = events[0]["args"]
    from_ = args["_from"]
    to = args["_to"]
    value = args["_value"]
    if from_ == A and to == B:
        assert value == -110
    elif from_ == B and to == A:
        assert value == 110
    else:
        assert (
            False
        ), "Wrong _from and _to in the event: were: {}, {}, but expected: {}, {}".format(
            from_, to, A, B
        )


def test_transfer_event(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    contract.functions.transfer(B, 110, 0, [B]).transact({"from": A})
    events = contract.events.Transfer.createFilter(fromBlock=0).get_all_entries()
    assert len(events) == 1
    args = events[0]["args"]
    from_ = args["_from"]
    to = args["_to"]
    value = args["_value"]
    assert from_ == A
    assert to == B
    assert value == 110


def test_update_trustline_add_users(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 50, 100).transact({"from": A})
    contract.functions.updateTrustline(A, 100, 50).transact({"from": B})
    assert len(contract.call().getUsers()) == 2


def test_update_set_account_add_users(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.setAccount(A, B, 50, 100, 0, 0, 0, 0, 0, 0).transact()
    assert len(contract.functions.getUsers().call()) == 2


def test_selfdestruct(currency_network_contract):
    currency_network_contract.functions.destruct().transact()
    with pytest.raises(BadFunctionCallOutput):  # contract does not exist
        currency_network_contract.functions.decimals().call()


def test_only_owner_selfdestruct(currency_network_contract, accounts):
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_contract.functions.destruct().transact({"from": accounts[1]})


CREDITLINE_WIDTH = 64
MAX_CREDITLINE = 2**CREDITLINE_WIDTH - 1


def test_max_transfer(currency_network_contract, accounts):
    A, B, *rest = accounts
    contract = currency_network_contract
    contract.functions.updateTrustline(B, MAX_CREDITLINE, MAX_CREDITLINE).transact({"from": A})
    contract.functions.updateTrustline(A, MAX_CREDITLINE, MAX_CREDITLINE).transact({"from": B})
    contract.functions.transfer(B, MAX_CREDITLINE, 0, [B]).transact({"from": A})

    assert contract.functions.balance(A, B).call() == -MAX_CREDITLINE


def test_overflow_max_transfer(currency_network_contract, accounts):
    A, B, *rest = accounts
    contract = currency_network_contract
    contract.functions.updateTrustline(B, MAX_CREDITLINE, MAX_CREDITLINE).transact({"from": A})
    contract.functions.updateTrustline(A, MAX_CREDITLINE, MAX_CREDITLINE).transact({"from": B})
    contract.functions.transfer(B, MAX_CREDITLINE, 0, [B]).transact({"from": A})
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(B, 1, 0, [B]).transact({"from": A})
