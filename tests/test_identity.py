#! pytest
import pytest
from eth_tester.exceptions import TransactionFailed
from hexbytes import HexBytes
from tldeploy.core import deploy_network, deploy_identity
from tldeploy.identity import (
    MetaTransaction,
    Identity,
    Delegate,
    UnexpectedIdentityContractException,
)
from tldeploy.signing import solidity_keccak, sign_msg_hash

from .conftest import EXTRA_DATA, EXPIRATION_TIME


def get_transaction_status(web3, tx_id):
    return bool(web3.eth.getTransactionReceipt(tx_id).get("status"))


@pytest.fixture(scope="session")
def delegate_address(accounts):
    return accounts[1]


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def owner_key(account_keys):
    return account_keys[0]


@pytest.fixture(scope="session")
def identity_contract(deploy_contract, web3, owner):
    identity_contract = deploy_contract("Identity")
    identity_contract.functions.init(owner).transact({"from": owner})
    web3.eth.sendTransaction(
        {"to": identity_contract.address, "from": owner, "value": 1000000}
    )
    return identity_contract


@pytest.fixture(scope="session")
def test_identity_contract(deploy_contract, web3, owner):
    test_identity_contract = deploy_contract("TestIdentity")
    test_identity_contract.functions.init(owner).transact({"from": owner})
    web3.eth.sendTransaction(
        {"to": test_identity_contract.address, "from": owner, "value": 1000000}
    )
    return test_identity_contract


@pytest.fixture(scope="session")
def identity(identity_contract, owner_key):
    return Identity(contract=identity_contract, owner_private_key=owner_key)


@pytest.fixture(scope="session")
def delegate(identity_contract, delegate_address, web3):
    return Delegate(
        delegate_address, web3=web3, identity_contract_abi=identity_contract.abi
    )


@pytest.fixture(scope="session")
def test_contract(deploy_contract):
    return deploy_contract("TestContract")


NETWORK_SETTING = {
    "name": "TestCoin",
    "symbol": "T",
    "decimals": 6,
    "fee_divisor": 0,
    "default_interest_rate": 0,
    "custom_interests": False,
    "expiration_time": EXPIRATION_TIME,
}


@pytest.fixture(scope="session")
def currency_network_contract(web3):
    return deploy_network(web3, **NETWORK_SETTING)


@pytest.fixture(scope="session")
def second_currency_network_contract(web3):
    return deploy_network(web3, **NETWORK_SETTING)


def test_init_already_init(test_identity_contract, accounts):
    with pytest.raises(TransactionFailed):
        test_identity_contract.functions.init(accounts[0]).transact(
            {"from": accounts[0]}
        )


def test_signature_from_owner(test_identity_contract, owner_key):

    data_to_sign = (1234).to_bytes(10, byteorder="big")
    hash = solidity_keccak(["bytes"], [data_to_sign])
    signature = sign_msg_hash(hash, owner_key)

    assert test_identity_contract.functions.validateSignature(hash, signature).call()


def test_signature_not_owner(test_identity_contract, account_keys):
    key = account_keys[1]

    data = (1234).to_bytes(10, byteorder="big")
    hash = solidity_keccak(["bytes"], [data])
    signature = sign_msg_hash(hash, key)

    assert not test_identity_contract.functions.validateSignature(
        hash, signature
    ).call()


def test_wrong_signature_from_owner(test_identity_contract, owner_key):

    data = (1234).to_bytes(10, byteorder="big")
    wrong_data = (12345678).to_bytes(10, byteorder="big")

    signature = owner_key.sign_msg(data).to_bytes()

    assert not test_identity_contract.functions.validateSignature(
        wrong_data, signature
    ).call()


def test_meta_transaction_signature_corresponds_to_clientlib_signature(
    identity, owner_key
):
    # Tests that the signature obtained from the contracts and the clientlib implementation match,
    # If this test needs to be changed, the corresponding test in the clientlib should also be changed
    # See: clientlib/tests/unit/IdentityWallet.test.ts: 'should sign meta-transaction'
    from_ = "0xF2E246BB76DF876Cef8b38ae84130F4F55De395b"
    to = "0x51a240271AB8AB9f9a21C82d9a85396b704E164d"
    value = 0
    data = "0x46432830000000000000000000000000000000000000000000000000000000000000000a"
    fees = 1
    currency_network_of_fees = "0x51a240271AB8AB9f9a21C82d9a85396b704E164d"
    extra_data = "0x"
    nonce = 1

    meta_transaction = MetaTransaction(
        from_=from_,
        to=to,
        value=value,
        data=data,
        fees=fees,
        currency_network_of_fees=currency_network_of_fees,
        extra_data=extra_data,
        nonce=nonce,
    )

    signature = identity.signed_meta_transaction(meta_transaction).signature

    assert (
        str(owner_key)
        == "0x0000000000000000000000000000000000000000000000000000000000000001"
    )
    assert (
        signature.hex()
        == "02a3c9abd0de925653c188b7f2e6e79ca032037371ef12a560116595508a"
        "51b65c1e4692878a87b491ef28e9ee560f7de0f2cb3f0981215134522750d42edce501"
    )


def test_delegated_transaction_hash(test_identity_contract, test_contract, accounts):
    to = accounts[3]
    from_ = accounts[1]
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = MetaTransaction.from_function_call(
        function_call, from_=from_, to=to, nonce=0
    )

    hash_by_contract = test_identity_contract.functions.testTransactionHash(
        meta_transaction.from_,
        meta_transaction.to,
        meta_transaction.value,
        meta_transaction.data,
        meta_transaction.fees,
        meta_transaction.currency_network_of_fees,
        meta_transaction.nonce,
        meta_transaction.extra_data,
    ).call()

    hash = meta_transaction.hash

    assert hash == HexBytes(hash_by_contract)


def test_delegated_transaction_function_call(identity, delegate, test_contract, web3):
    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    meta_transaction = identity.filled_and_signed_meta_transaction(meta_transaction)
    tx_id = delegate.send_signed_meta_transaction(meta_transaction)

    event = test_contract.events.TestEvent.createFilter(fromBlock=0).get_all_entries()[
        0
    ]["args"]

    assert get_transaction_status(web3, tx_id)
    assert event["from"] == identity.address
    assert event["value"] == 0
    assert event["argument"] == argument


def test_delegated_transaction_transfer(web3, identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(to=to, value=value)

    balance_before = web3.eth.getBalance(to)
    meta_transaction = identity.filled_and_signed_meta_transaction(meta_transaction)
    tx_id = delegate.send_signed_meta_transaction(meta_transaction)

    balance_after = web3.eth.getBalance(to)

    assert get_transaction_status(web3, tx_id)
    assert balance_after - balance_before == value


def test_delegated_transaction_same_tx_fails(identity, delegate, accounts, web3):
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(to=to, value=value)
    meta_transaction = identity.filled_and_signed_meta_transaction(meta_transaction)
    delegate.send_signed_meta_transaction(meta_transaction)

    tx_id = delegate.send_signed_meta_transaction(meta_transaction)
    assert get_transaction_status(web3, tx_id) is False


def test_delegated_transaction_wrong_from(
    identity_contract, delegate_address, accounts, owner_key
):
    from_ = accounts[3]
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(from_=from_, to=to, value=value, nonce=0).signed(
        owner_key
    )

    with pytest.raises(TransactionFailed):
        identity_contract.functions.executeTransaction(
            meta_transaction.from_,
            meta_transaction.to,
            meta_transaction.value,
            meta_transaction.data,
            meta_transaction.fees,
            meta_transaction.currency_network_of_fees,
            meta_transaction.nonce,
            meta_transaction.extra_data,
            meta_transaction.signature,
        ).transact({"from": delegate_address})


def test_delegated_transaction_wrong_signature(
    identity, delegate, accounts, account_keys, web3
):
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(
        from_=identity.address, to=to, value=value, nonce=0
    ).signed(account_keys[3])

    tx_id = delegate.send_signed_meta_transaction(meta_transaction)
    assert get_transaction_status(web3, tx_id) is False


def test_delegated_transaction_success_event(identity, delegate, test_contract):
    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    event = identity.contract.events.TransactionExecution.createFilter(
        fromBlock=0
    ).get_all_entries()[0]["args"]

    assert event["hash"] == meta_transaction.hash
    assert event["status"] is True


def test_delegated_transaction_fail_event(identity, delegate, test_contract):
    to = test_contract.address
    function_call = test_contract.functions.fails()

    meta_transaction = identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    event = identity.contract.events.TransactionExecution.createFilter(
        fromBlock=0
    ).get_all_entries()[0]["args"]

    assert event["hash"] == meta_transaction.hash
    assert event["status"] is False


def test_delegated_transaction_trustlines_flow(
    currency_network_contract, identity, delegate, accounts
):
    A = identity.address
    B = accounts[3]
    to = currency_network_contract.address

    function_call = currency_network_contract.functions.updateCreditlimits(B, 100, 100)
    meta_transaction = identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    currency_network_contract.functions.updateCreditlimits(A, 100, 100).transact(
        {"from": B}
    )

    function_call = currency_network_contract.functions.transfer(
        100, 0, [A, B], EXTRA_DATA
    )
    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    meta_transaction = identity.filled_and_signed_meta_transaction(meta_transaction)
    delegate.send_signed_meta_transaction(meta_transaction)

    assert currency_network_contract.functions.balance(A, B).call() == -100


def test_delegated_transaction_nonce_zero(identity, delegate, web3, accounts):
    to = accounts[2]
    value1 = 1000
    value2 = 1001

    balance_before = web3.eth.getBalance(to)

    meta_transaction1 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value1, nonce=0)
    )
    meta_transaction2 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value2, nonce=0)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)
    delegate.send_signed_meta_transaction(meta_transaction2)

    balance_after = web3.eth.getBalance(to)

    assert balance_after - balance_before == value1 + value2


def test_delegated_transaction_nonce_increase(identity, delegate, web3, accounts):
    to = accounts[2]
    value = 1000

    balance_before = web3.eth.getBalance(to)

    meta_transaction1 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=2)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)
    delegate.send_signed_meta_transaction(meta_transaction2)

    balance_after = web3.eth.getBalance(to)

    assert balance_after - balance_before == value + value


def test_delegated_transaction_same_nonce_fails(identity, delegate, web3, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction1 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)

    tx_id = delegate.send_signed_meta_transaction(meta_transaction2)
    assert get_transaction_status(web3, tx_id) is False


def test_delegated_transaction_nonce_gap_fails(identity, delegate, web3, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction1 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=3)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)

    tx_id = delegate.send_signed_meta_transaction(meta_transaction2)
    assert get_transaction_status(web3, tx_id) is False


def test_validate_same_tx(identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    assert not delegate.validate_meta_transaction(meta_transaction)


def test_validate_from_no_code(identity_contract, delegate, accounts, owner_key):
    from_ = accounts[3]
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(from_=from_, to=to, value=value, nonce=0).signed(
        owner_key
    )

    with pytest.raises(UnexpectedIdentityContractException):
        delegate.validate_meta_transaction(meta_transaction)


def test_validate_from_wrong_contract(
    identity_contract, delegate, accounts, owner_key, currency_network_contract
):
    from_ = currency_network_contract.address
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(from_=from_, to=to, value=value, nonce=0).signed(
        owner_key
    )

    with pytest.raises(UnexpectedIdentityContractException):
        delegate.validate_meta_transaction(meta_transaction)


def test_validate_wrong_signature(identity, delegate, accounts, account_keys):
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(
        from_=identity.address, to=to, value=value, nonce=0
    ).signed(account_keys[3])

    assert not delegate.validate_meta_transaction(meta_transaction)


def test_validate_same_nonce_fails(identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction1 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)

    assert not delegate.validate_meta_transaction(meta_transaction2)


def test_validate_nonce_gap_fails(identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction1 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=3)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)

    assert not delegate.validate_meta_transaction(meta_transaction2)


def test_validate_valid_transfer(identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value)
    )

    assert delegate.validate_meta_transaction(meta_transaction)


def test_validate_valid_nonce_increase(identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction1 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=2)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)

    assert delegate.validate_meta_transaction(meta_transaction2)


def test_estimate_gas(identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value)
    )

    assert isinstance(
        delegate.estimate_gas_signed_meta_transaction(meta_transaction), int
    )


def test_deploy_identity(web3, delegate, owner, owner_key, test_contract):
    identity_contract = deploy_identity(web3, owner)

    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = MetaTransaction.from_function_call(
        function_call, to=to, from_=identity_contract.address, nonce=0
    ).signed(owner_key)
    delegate.send_signed_meta_transaction(meta_transaction)

    assert (
        len(test_contract.events.TestEvent.createFilter(fromBlock=0).get_all_entries())
        > 0
    )


def test_next_nonce(identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction1 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=2)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)
    delegate.send_signed_meta_transaction(meta_transaction2)

    assert delegate.get_next_nonce(identity.address) == 3


def test_meta_transaction_with_fees_increases_debt(
    currency_network_contract, identity, delegate, delegate_address, accounts
):
    A = identity.address
    B = accounts[3]
    to = currency_network_contract.address
    fees = 123

    function_call = currency_network_contract.functions.updateCreditlimits(B, 100, 100)
    meta_transaction = identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to, fees=fees)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    assert (
        currency_network_contract.functions.getDebt(A, delegate_address).call() == fees
    )


def test_failing_meta_transaction_with_fees_does_not_increases_debt(
    currency_network_contract, identity, delegate, delegate_address, accounts
):
    A = identity.address
    B = accounts[3]
    to = currency_network_contract.address
    fees = 123

    function_call = currency_network_contract.functions.transfer(100, 100, [A, B], b"")
    meta_transaction = identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to, fees=fees)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    assert currency_network_contract.functions.getDebt(A, delegate_address).call() == 0


def test_tracking_delegation_fee_in_different_network(
    currency_network_contract,
    second_currency_network_contract,
    identity,
    delegate,
    delegate_address,
    accounts,
):
    A = identity.address
    B = accounts[3]
    to = currency_network_contract.address
    fees = 123

    function_call = currency_network_contract.functions.updateCreditlimits(B, 100, 100)
    meta_transaction = identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(
            function_call,
            to=to,
            fees=fees,
            currency_network_of_fees=second_currency_network_contract.address,
        )
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    assert currency_network_contract.functions.getDebt(A, delegate_address).call() == 0
    assert (
        second_currency_network_contract.functions.getDebt(A, delegate_address).call()
        == fees
    )
