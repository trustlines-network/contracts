import time

import pytest
import eth_tester.exceptions
from math import exp

from eth_tester.exceptions import TransactionFailed
from tldeploy.core import deploy_network
from .conftest import EXTRA_DATA, EXPIRATION_TIME, MAX_UINT_64

trustlines = [
    (0, 1, 2000000000, 2000000000),
    (1, 2, 200, 250),
    (2, 3, 300, 350),
    (3, 4, 400, 450),
    (0, 4, 500, 550),
]  # (A, B, clAB, clBA)

SECONDS_PER_YEAR = 60 * 60 * 24 * 365


@pytest.fixture(scope="session")
def test_currency_network_contract(deploy_contract):
    return deploy_contract("TestCurrencyNetwork")


@pytest.fixture(scope="session")
def currency_network_contract_no_interests(web3):
    return deploy_network(
        web3,
        "TestCoin",
        "T",
        decimals=6,
        fee_divisor=0,
        default_interest_rate=0,
        custom_interests=False,
        prevent_mediator_interests=False,
        currency_network_contract_name="TestCurrencyNetwork",
        expiration_time=EXPIRATION_TIME,
    )


@pytest.fixture(scope="session")
def currency_network_contract_default_interests(web3):
    return deploy_network(
        web3,
        "TestCoin",
        "T",
        decimals=6,
        fee_divisor=0,
        default_interest_rate=100,
        custom_interests=False,
        prevent_mediator_interests=False,
        currency_network_contract_name="TestCurrencyNetwork",
        expiration_time=EXPIRATION_TIME,
    )


@pytest.fixture(scope="session")
def currency_network_contract_negative_interests(web3):
    return deploy_network(
        web3,
        "TestCoin",
        "T",
        decimals=6,
        fee_divisor=0,
        default_interest_rate=-100,
        custom_interests=False,
        prevent_mediator_interests=False,
        currency_network_contract_name="TestCurrencyNetwork",
        expiration_time=EXPIRATION_TIME,
    )


@pytest.fixture(scope="session")
def currency_network_contract_custom_interests_safe_ripple(web3):
    return deploy_network(
        web3,
        "TestCoin",
        "T",
        decimals=6,
        fee_divisor=0,
        default_interest_rate=0,
        custom_interests=True,
        prevent_mediator_interests=True,
        currency_network_contract_name="TestCurrencyNetwork",
        expiration_time=EXPIRATION_TIME,
    )


@pytest.fixture(params=["transfer", "transferReceiverPays"])
def transfer_function_name(request):
    return request.param


@pytest.mark.parametrize(
    "balance, start_time, end_time, interest_rate_given, interest_rate_received, result",
    [
        (1000, 0, SECONDS_PER_YEAR, 1000, 0, 1000 * exp(0.1)),
        (1000, 0, SECONDS_PER_YEAR, -1000, 0, 1000 * exp(-0.1)),
        (-1000, 0, SECONDS_PER_YEAR, 0, 1000, -1000 * exp(0.1)),
        (1000, 0, SECONDS_PER_YEAR, 100, 100, 1000 * exp(0.01)),
        (10 ** 17, 0, SECONDS_PER_YEAR, 200, 200, 10 ** 17 * exp(0.02)),
        (1000, SECONDS_PER_YEAR, 2 * SECONDS_PER_YEAR, 1000, 1000, 1000 * exp(0.1)),
        (MAX_UINT_64, 0, SECONDS_PER_YEAR, 1000, 0, MAX_UINT_64),
        (-MAX_UINT_64, 0, SECONDS_PER_YEAR, 1000, 1000, -MAX_UINT_64),
        (MAX_UINT_64 - 10, 0, SECONDS_PER_YEAR, 1000, 1000, MAX_UINT_64),
        (-MAX_UINT_64 + 10, 0, SECONDS_PER_YEAR, 1000, 1000, -MAX_UINT_64),
        (1000, 0, 2 ** 32 - 1, 2 ** 15 - 1, 0, MAX_UINT_64),
        (1000, 0, 2 ** 32 - 1, -(2 ** 15), 0, 0),
        (-1000, 0, 2 ** 32 - 1, 0, 2 ** 15 - 1, -MAX_UINT_64),
        (-1000, 0, 2 ** 32 - 1, 0, -(2 ** 15), 0),
        (1000, 1, 0, 1000, 0, None),
    ],
)
def test_interest_calculation(
    test_currency_network_contract,
    balance,
    start_time,
    end_time,
    interest_rate_given,
    interest_rate_received,
    result,
):

    if result is None:
        with pytest.raises(TransactionFailed):
            test_currency_network_contract.functions.testCalculateBalanceWithInterests(
                balance,
                start_time,
                end_time,
                interest_rate_given,
                interest_rate_received,
            ).call()
    else:
        assert test_currency_network_contract.functions.testCalculateBalanceWithInterests(
            balance, start_time, end_time, interest_rate_given, interest_rate_received
        ).call() == pytest.approx(
            result, abs=1
        )


def test_interests_positive_balance(
    chain, currency_network_contract_default_interests, accounts, transfer_function_name
):
    """Tests interests with a default setting"""

    contract = currency_network_contract_default_interests
    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0],
        accounts[1],
        2000000000,
        2000000000,
        100,
        100,
        False,
        current_time,
        100000000,
    ).transact()

    chain.time_travel(current_time + SECONDS_PER_YEAR)
    getattr(contract.functions, transfer_function_name)(
        1, 2, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})

    balance = contract.functions.balance(accounts[0], accounts[1]).call()

    # for small balances and interests not more than the smallest unit
    assert balance + 1 == pytest.approx(100000000 * exp(0.01), abs=1)


def test_interests_high_value(
    chain,
    currency_network_contract_custom_interests_safe_ripple,
    accounts,
    transfer_function_name,
):
    """Test interests with high interests"""

    contract = currency_network_contract_custom_interests_safe_ripple

    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0],
        accounts[1],
        2000000000,
        2000000000,
        2000,
        2000,
        False,
        current_time,
        1000000000000000000,
    ).transact()

    chain.time_travel(current_time + SECONDS_PER_YEAR)
    getattr(contract.functions, transfer_function_name)(
        1, 2, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})

    balance = contract.functions.balance(accounts[0], accounts[1]).call()

    # for big balances and interests not more than 1%
    assert balance + 1 == pytest.approx(1000000000000000000 * exp(0.20), rel=0.01)  # 1%


def test_interests_negative_balance(
    chain, currency_network_contract_default_interests, accounts, transfer_function_name
):
    """Tests interests with a default setting with a negative balance"""

    contract = currency_network_contract_default_interests
    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0],
        accounts[1],
        2000000000,
        2000000000,
        100,
        100,
        False,
        current_time,
        -100000000,
    ).transact()
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    chain.time_travel(current_time + SECONDS_PER_YEAR)
    getattr(contract.functions, transfer_function_name)(
        1, 2, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})

    balance = contract.functions.balance(accounts[0], accounts[1]).call()

    # for big balances and interests not more than 1%
    assert balance + 1 == pytest.approx(-100000000 * exp(0.01), abs=1)


def test_no_interests(
    chain, currency_network_contract_no_interests, accounts, transfer_function_name
):
    """Tests that we can have a network with no interests"""

    contract = currency_network_contract_no_interests
    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0],
        accounts[1],
        2000000000,
        2000000000,
        0,
        0,
        False,
        current_time,
        100000000,
    ).transact()
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    chain.time_travel(current_time + SECONDS_PER_YEAR)
    getattr(contract.functions, transfer_function_name)(
        1, 2, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})

    balance = contract.functions.balance(accounts[0], accounts[1]).call()

    assert balance == 100000000 - 1


def test_custom_interests(
    chain,
    currency_network_contract_custom_interests_safe_ripple,
    accounts,
    transfer_function_name,
):
    """Tests custom interests setting, set with setAccount"""

    contract = currency_network_contract_custom_interests_safe_ripple
    contract.functions.setAccount(
        accounts[0], accounts[1], 0, 2000000000, 0, 1234, False, 0, 0
    ).transact()
    current_time = int(time.time())
    chain.time_travel(current_time + SECONDS_PER_YEAR)
    getattr(contract.functions, transfer_function_name)(
        100000000, 2000000, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})

    chain.time_travel(current_time + 2 * SECONDS_PER_YEAR)
    getattr(contract.functions, transfer_function_name)(
        1, 2, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})

    balance = contract.functions.balance(accounts[0], accounts[1]).call()

    assert balance + 1 == pytest.approx(-100000000 * exp(0.1234), rel=0.01)  # 1%


def test_custom_interests_postive_balance(
    chain,
    currency_network_contract_custom_interests_safe_ripple,
    accounts,
    transfer_function_name,
):
    """Tests custom interests setting, set with setAccount"""

    contract = currency_network_contract_custom_interests_safe_ripple
    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0], accounts[1], 0, 2000000000, 1234, 0, False, current_time, 100000000
    ).transact()

    chain.time_travel(current_time + SECONDS_PER_YEAR)
    getattr(contract.functions, transfer_function_name)(
        1, 2, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})

    balance = contract.functions.balance(accounts[0], accounts[1]).call()

    assert balance + 1 == pytest.approx(100000000 * exp(0.1234), rel=0.01)  # 1%


def test_setting_default_and_custom_interests_fails(web3):
    """Tests that we cannot set default and custom interests at the same time"""
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        deploy_network(
            web3,
            "TestCoin",
            "T",
            6,
            0,
            default_interest_rate=1,
            custom_interests=True,
            prevent_mediator_interests=False,
        )


def test_safe_interest_allows_direct_transactions(
    currency_network_contract_custom_interests_safe_ripple,
    accounts,
    transfer_function_name,
):
    """Tests that the safeInterestRippling does not prevent legit transactions"""

    contract = currency_network_contract_custom_interests_safe_ripple
    contract.functions.setAccount(
        accounts[0], accounts[1], 1000000, 2000000, 100, 200, False, 0, 0
    ).transact()
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    getattr(contract.functions, transfer_function_name)(
        1, 2, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})


def test_safe_interest_allows_transactions_mediated(
    chain,
    currency_network_contract_custom_interests_safe_ripple,
    accounts,
    transfer_function_name,
):
    """Tests that the safeInterestRippling does not prevent legit transactions"""

    contract = currency_network_contract_custom_interests_safe_ripple
    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0], accounts[1], 1000000, 2000000, 100, 200, False, current_time, 0
    ).transact()
    contract.functions.setAccount(
        accounts[1], accounts[2], 1000000, 2000000, 100, 200, False, current_time, 0
    ).transact()
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    getattr(contract.functions, transfer_function_name)(
        1, 2, [accounts[0], accounts[1], accounts[2]], EXTRA_DATA
    ).transact({"from": accounts[0]})


def test_safe_interest_disallows_transactions_mediated_if_interests_increase(
    chain,
    currency_network_contract_custom_interests_safe_ripple,
    accounts,
    transfer_function_name,
):
    """Tests that the safeInterestRippling prevents transaction where the mediator would loose money,
    because of interests"""

    contract = currency_network_contract_custom_interests_safe_ripple
    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0], accounts[1], 1000000, 2000000, 200, 100, False, current_time, 0
    ).transact()
    contract.functions.setAccount(
        accounts[1], accounts[2], 1000000, 2000000, 100, 200, False, current_time, 0
    ).transact()

    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        getattr(contract.functions, transfer_function_name)(
            1, 2, [accounts[0], accounts[1], accounts[2]], EXTRA_DATA
        ).transact({"from": accounts[0]})


def test_safe_interest_allows_transactions_mediated_solves_imbalance(
    chain,
    currency_network_contract_custom_interests_safe_ripple,
    accounts,
    transfer_function_name,
):
    """Tests that the safeInterestRippling allows transactions that reduce imbalances"""

    contract = currency_network_contract_custom_interests_safe_ripple
    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0], accounts[1], 1000000, 2000000, 200, 100, False, current_time, 100
    ).transact()
    contract.functions.setAccount(
        accounts[1], accounts[2], 1000000, 2000000, 100, 200, False, current_time, 100
    ).transact()

    getattr(contract.functions, transfer_function_name)(
        1, 2, [accounts[0], accounts[1], accounts[2]], EXTRA_DATA
    ).transact({"from": accounts[0]})


def test_safe_interest_disallows_transactions_mediated_solves_imbalance_but_overflows(
    chain,
    currency_network_contract_custom_interests_safe_ripple,
    accounts,
    transfer_function_name,
):
    """Tests that the safeInterestRippling disallows transactions that make mediators loose money"""

    contract = currency_network_contract_custom_interests_safe_ripple
    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0], accounts[1], 1000000, 2000000, 200, 100, False, current_time, 100
    ).transact()
    contract.functions.setAccount(
        accounts[1], accounts[2], 1000000, 2000000, 100, 200, False, current_time, 100
    ).transact()

    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        getattr(contract.functions, transfer_function_name)(
            201, 2, [accounts[0], accounts[1], accounts[2]], EXTRA_DATA
        ).transact({"from": accounts[0]})


def test_negative_interests_default_positive_balance(
    chain,
    currency_network_contract_negative_interests,
    accounts,
    transfer_function_name,
):
    """Tests interests with a default setting with negative interests"""

    contract = currency_network_contract_negative_interests
    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0],
        accounts[1],
        2000000000,
        2000000000,
        -100,
        -100,
        False,
        current_time,
        100000000,
    ).transact()
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    chain.time_travel(current_time + SECONDS_PER_YEAR)
    getattr(contract.functions, transfer_function_name)(
        1, 2, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})

    balance = contract.functions.balance(accounts[0], accounts[1]).call()

    assert balance + 1 == pytest.approx(100000000 * exp(-0.01), abs=1)


def test_negative_interests_default_negative_balance(
    chain,
    currency_network_contract_negative_interests,
    accounts,
    transfer_function_name,
):
    """Tests interests with negative interests with a negative balance"""

    contract = currency_network_contract_negative_interests
    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0],
        accounts[1],
        2000000000,
        2000000000,
        -100,
        -100,
        False,
        current_time,
        -100000000,
    ).transact()
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    chain.time_travel(current_time + SECONDS_PER_YEAR)
    getattr(contract.functions, transfer_function_name)(
        1, 2, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})

    balance = contract.functions.balance(accounts[0], accounts[1]).call()

    assert balance + 1 == pytest.approx(-100000000 * exp(-0.01), abs=1)


CREDITLINE_WIDTH = 64
BALANCE_WIDTH = 72
INTEREST_WIDTH = 16


def test_interests_overflow(
    chain, currency_network_contract_custom_interests_safe_ripple, accounts
):
    """Test that the interests will not put the balance above max uint64"""
    contract = currency_network_contract_custom_interests_safe_ripple
    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0],
        accounts[1],
        2 ** CREDITLINE_WIDTH - 1,
        2 ** CREDITLINE_WIDTH - 1,
        2 ** (INTEREST_WIDTH - 1) - 1,
        2 ** (INTEREST_WIDTH - 1) - 1,
        False,
        current_time,
        2 ** CREDITLINE_WIDTH - 1,
    ).transact()
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    chain.time_travel(current_time + int(1.6923 * SECONDS_PER_YEAR))
    contract.functions.transfer(1, 2, [accounts[0], accounts[1]], EXTRA_DATA).transact(
        {"from": accounts[0]}
    )

    balance = contract.functions.balance(accounts[0], accounts[1]).call()

    assert balance + 1 == 2 ** CREDITLINE_WIDTH - 1


def test_interests_underflow(
    chain, currency_network_contract_custom_interests_safe_ripple, accounts
):
    """Test that the interests will not put the balance below min uint64"""
    contract = currency_network_contract_custom_interests_safe_ripple
    current_time = int(time.time())
    chain.time_travel(current_time + 10)
    contract.functions.setAccount(
        accounts[0],
        accounts[1],
        2 ** CREDITLINE_WIDTH - 1,
        2 ** CREDITLINE_WIDTH - 1,
        2 ** (INTEREST_WIDTH - 1) - 1,
        2 ** (INTEREST_WIDTH - 1) - 1,
        False,
        current_time,
        -(2 ** CREDITLINE_WIDTH - 1),
    ).transact()
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    chain.time_travel(current_time + int(2.23 * SECONDS_PER_YEAR))

    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(
            1, 0, [accounts[0], accounts[1]], EXTRA_DATA
        ).transact({"from": accounts[0]})

    contract.functions.transfer(1, 0, [accounts[1], accounts[0]], EXTRA_DATA).transact(
        {"from": accounts[1]}
    )
    balance = contract.functions.balance(accounts[0], accounts[1]).call()

    assert balance - 1 == -(2 ** CREDITLINE_WIDTH - 1)


def test_interests_over_change_in_trustline(
    chain, currency_network_contract_custom_interests_safe_ripple, accounts
):
    contract = currency_network_contract_custom_interests_safe_ripple
    current_time = int(time.time())
    chain.time_travel(current_time + 10)

    contract.functions.updateTrustline(
        accounts[0], 100000, 100000, 0, 0, False
    ).transact({"from": accounts[1]})
    contract.functions.updateTrustline(
        accounts[1], 100000, 100000, 0, 0, False
    ).transact({"from": accounts[0]})
    contract.functions.transfer(
        10000, 0, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})

    chain.time_travel(current_time + SECONDS_PER_YEAR)

    contract.functions.updateTrustline(
        accounts[0], 100000, 100000, 1000, 1000, False
    ).transact({"from": accounts[1]})
    contract.functions.updateTrustline(
        accounts[1], 100000, 100000, 1000, 1000, False
    ).transact({"from": accounts[0]})

    contract.functions.transfer(1, 0, [accounts[0], accounts[1]], EXTRA_DATA).transact(
        {"from": accounts[0]}
    )

    assert contract.functions.balance(accounts[0], accounts[1]).call() == -10001


def test_payback_interests_even_over_creditline(
    chain, currency_network_contract_custom_interests_safe_ripple, accounts
):
    contract = currency_network_contract_custom_interests_safe_ripple
    current_time = int(time.time())
    chain.time_travel(current_time + 10)

    contract.functions.updateTrustline(
        accounts[0], 10000, 10000, 200, 200, False
    ).transact({"from": accounts[1]})
    contract.functions.updateTrustline(
        accounts[1], 10000, 10000, 200, 200, False
    ).transact({"from": accounts[0]})
    contract.functions.transfer(
        10000, 0, [accounts[1], accounts[0]], EXTRA_DATA
    ).transact({"from": accounts[1]})

    chain.time_travel(current_time + SECONDS_PER_YEAR)

    contract.functions.transfer(
        10202, 0, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})

    assert contract.functions.balance(accounts[0], accounts[1]).call() == pytest.approx(
        0, abs=2
    )


def test_interests_over_creditline_is_usable(
    chain, currency_network_contract_custom_interests_safe_ripple, accounts
):
    contract = currency_network_contract_custom_interests_safe_ripple
    current_time = int(time.time())
    chain.time_travel(current_time + 10)

    contract.functions.updateTrustline(
        accounts[0], 10000, 10000, 200, 200, False
    ).transact({"from": accounts[1]})
    contract.functions.updateTrustline(
        accounts[1], 10000, 10000, 200, 200, False
    ).transact({"from": accounts[0]})
    contract.functions.transfer(
        10000, 0, [accounts[1], accounts[0]], EXTRA_DATA
    ).transact({"from": accounts[1]})

    chain.time_travel(current_time + SECONDS_PER_YEAR)

    contract.functions.transfer(1, 0, [accounts[0], accounts[1]], EXTRA_DATA).transact(
        {"from": accounts[0]}
    )

    assert contract.functions.balance(accounts[0], accounts[1]).call() == pytest.approx(
        10201, abs=2
    )


def test_correct_balance_update_event_on_interest_rate_change(
    chain, currency_network_contract_custom_interests_safe_ripple, accounts
):
    contract = currency_network_contract_custom_interests_safe_ripple
    current_time = int(time.time())
    chain.time_travel(current_time + 10)

    # Set trustline
    contract.functions.updateTrustline(
        accounts[0], 10000, 10000, 100, 100, False
    ).transact({"from": accounts[1]})
    contract.functions.updateTrustline(
        accounts[1], 10000, 10000, 100, 100, False
    ).transact({"from": accounts[0]})
    contract.functions.transfer(
        10000, 0, [accounts[1], accounts[0]], EXTRA_DATA
    ).transact({"from": accounts[1]})

    # Time travel
    chain.time_travel(current_time + SECONDS_PER_YEAR)

    # Update trustline
    contract.functions.updateTrustline(
        accounts[0], 11000, 11000, 200, 200, False
    ).transact({"from": accounts[1]})
    contract.functions.updateTrustline(
        accounts[1], 11000, 11000, 200, 200, False
    ).transact({"from": accounts[0]})

    # Check event
    events = contract.events.BalanceUpdate.createFilter(fromBlock=0).get_all_entries()
    args = events[-1]["args"]
    from_ = args["_from"]
    to = args["_to"]
    value = args["_value"]

    assert from_ in [accounts[0], accounts[1]]
    assert to in [accounts[0], accounts[1]]
    assert from_ != to

    assert contract.functions.balance(from_, to).call() == value
