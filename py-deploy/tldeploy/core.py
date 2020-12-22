# This file has been copied and adapted from the trustlines-contracts project.
# We like to get rid of the populus dependency and we don't want to compile the
# contracts when running tests in this project.

import collections
from typing import Dict, Iterable

from deploy_tools import deploy_compiled_contract
from deploy_tools.deploy import (
    increase_transaction_options_nonce,
    send_function_call_transaction as wait_for_successfull_call,
    _build_and_sign_transaction,
    _set_from_address,
)
from hexbytes import HexBytes
from web3 import Web3
from tlbin import load_packaged_contracts


# lazily load the contracts, so the compile_contracts fixture has a chance to
# set TRUSTLINES_CONTRACTS_JSON
class LazyContractsLoader(collections.UserDict):
    def __getitem__(self, *args):
        if not self.data:
            self.data = load_packaged_contracts()
        return super().__getitem__(*args)


contracts = LazyContractsLoader()


def get_contract_interface(contract_name):
    return contracts[contract_name]


def deploy(
    contract_name,
    *,
    web3: Web3,
    transaction_options: Dict = None,
    private_key: bytes = None,
    constructor_args=(),
):
    if transaction_options is None:
        transaction_options = {}

    contract_interface = contracts[contract_name]
    return deploy_compiled_contract(
        abi=contract_interface["abi"],
        bytecode=contract_interface["bytecode"],
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
        constructor_args=constructor_args,
    )


def deploy_exchange(
    *, web3: Web3, transaction_options: Dict = None, private_key: bytes = None
):
    if transaction_options is None:
        transaction_options = {}

    exchange = deploy(
        "Exchange",
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )
    increase_transaction_options_nonce(transaction_options)
    return exchange


def deploy_unw_eth(
    *,
    web3: Web3,
    transaction_options: Dict = None,
    private_key: bytes = None,
    exchange_address=None,
):
    if transaction_options is None:
        transaction_options = {}

    unw_eth = deploy(
        "UnwEth",
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )

    increase_transaction_options_nonce(transaction_options)

    if exchange_address is not None:
        if exchange_address is not None:
            function_call = unw_eth.functions.addAuthorizedAddress(exchange_address)
            wait_for_successfull_call(
                function_call,
                web3=web3,
                transaction_options=transaction_options,
                private_key=private_key,
            )
            increase_transaction_options_nonce(transaction_options)

    return unw_eth


def deploy_network(
    web3,
    name,
    symbol,
    decimals,
    expiration_time,
    fee_divisor=0,
    default_interest_rate=0,
    custom_interests=True,
    prevent_mediator_interests=False,
    exchange_address=None,
    currency_network_contract_name=None,
    transaction_options: Dict = None,
    private_key=None,
    authorized_addresses=None,
):
    if transaction_options is None:
        transaction_options = {}
    if authorized_addresses is None:
        authorized_addresses = []

    # CurrencyNetwork is the standard contract to deploy, If we're running
    # tests or trying to export data for testing the python implementation of
    # private functions, we may want deploy the TestCurrencyNetwork contract
    # instead.
    if currency_network_contract_name is None:
        currency_network_contract_name = "CurrencyNetwork"

    currency_network = deploy(
        currency_network_contract_name,
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )
    increase_transaction_options_nonce(transaction_options)

    if exchange_address is not None:
        authorized_addresses.append(exchange_address)

    init_function_call = currency_network.functions.init(
        name,
        symbol,
        decimals,
        fee_divisor,
        default_interest_rate,
        custom_interests,
        prevent_mediator_interests,
        expiration_time,
        authorized_addresses,
    )

    wait_for_successfull_call(
        init_function_call,
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )
    increase_transaction_options_nonce(transaction_options)

    return currency_network


def deploy_networks(
    web3,
    network_settings,
    currency_network_contract_name=None,
    transaction_options: Dict = None,
):
    exchange = deploy_exchange(web3=web3)
    unw_eth = deploy_unw_eth(web3=web3, exchange_address=exchange.address)

    networks = [
        deploy_network(
            web3,
            exchange_address=exchange.address,
            currency_network_contract_name=currency_network_contract_name,
            transaction_options=transaction_options,
            **network_setting,
        )
        for network_setting in network_settings
    ]

    return networks, exchange, unw_eth


def deploy_identity(
    web3, owner_address, chain_id=None, transaction_options: Dict = None
):
    if transaction_options is None:
        transaction_options = {}
    identity = deploy("Identity", web3=web3, transaction_options=transaction_options)
    increase_transaction_options_nonce(transaction_options)
    if chain_id is None:
        chain_id = get_chain_id(web3)
    function_call = identity.functions.init(owner_address, chain_id)
    wait_for_successfull_call(
        function_call, web3=web3, transaction_options=transaction_options
    )
    increase_transaction_options_nonce(transaction_options)

    return identity


def get_chain_id(web3):
    return int(web3.eth.chainId)


class NetworkMigrater:
    def __init__(
        self,
        web3,
        old_currency_network_address: str,
        new_currency_network_address: str,
        transaction_options: Dict = None,
        private_key: str = None,
        max_tx_queue_size=10,
    ):
        self.web3 = web3

        old_network_interface = get_contract_interface("CurrencyNetwork")
        self.old_network = web3.eth.contract(
            address=old_currency_network_address, abi=old_network_interface["abi"]
        )
        new_network_interface = get_contract_interface("CurrencyNetworkOwnable")
        self.new_network = web3.eth.contract(
            address=new_currency_network_address, abi=new_network_interface["abi"]
        )
        self.users = set(self.old_network.functions.getUsers().call())

        self.transaction_options = transaction_options
        if transaction_options is None:
            self.transaction_options = {}

        self.private_key = private_key
        self.max_tx_queue_size = max_tx_queue_size
        self.tx_queue = set()

    def migrate_network(self):
        assert (
            self.old_network.functions.isNetworkFrozen().call()
        ), "Old contract not frozen"
        assert (
            self.new_network.functions.isNetworkFrozen().call()
        ), "New contract not frozen"
        assert (
            self.old_network.functions.name().call()
            == self.new_network.functions.name().call()
        ), "New and old contracts name do not match"

        self.migrate_accounts()
        self.migrate_on_boarders()
        self.migrate_debts()
        self.unfreeze_network()
        self.remove_owner()

    def migrate_accounts(self):
        for user in self.users:
            friends = set(self.old_network.functions.getFriends(user).call())
            for friend in friends:
                if user < friend:
                    # For each (user, friend) pair we only need to migrate the account once
                    # We arbitrarily decide not to migrate in the case user < friend
                    continue
                (
                    creditline_ab,
                    creditline_ba,
                    interest_ab,
                    interest_ba,
                    is_frozen,
                    mtime,
                    balance_ab,
                ) = self.old_network.functions.getAccount(user, friend).call()
                set_account_call = self.new_network.functions.setAccount(
                    user,
                    friend,
                    creditline_ab,
                    creditline_ba,
                    interest_ab,
                    interest_ba,
                    is_frozen,
                    mtime,
                    balance_ab,
                )
                self.call_contract_function_with_tx(set_account_call)
        self.wait_for_successfull_txs_in_queue()

    def migrate_on_boarders(self):
        for user in self.users:
            on_boarder = self.old_network.functions.onboarder(user).call()
            set_on_boarder_call = self.new_network.functions.setOnboarder(
                user, on_boarder
            )
            self.call_contract_function_with_tx(set_on_boarder_call)
        self.wait_for_successfull_txs_in_queue()

    def migrate_debts(self):
        # We have to use events to retrieve the debts
        # We cannot use `self.users` as some non users could have set a debt
        debts = self.get_all_debts()
        for debtor in debts.keys():
            for creditor in debts[debtor].keys():
                set_debt_call = self.new_network.functions.setDebt(
                    debtor, creditor, debts[debtor][creditor]
                )
                self.call_contract_function_with_tx(set_debt_call)
        self.wait_for_successfull_txs_in_queue()

    def get_all_debts(self):
        all_debt_updates = self.old_network.events.DebtUpdate().getLogs(fromBlock=0)
        debts = collections.defaultdict(lambda: {})

        for debt_update in all_debt_updates:
            creditor = debt_update["args"]["_creditor"]
            debtor = debt_update["args"]["_debtor"]
            value = debt_update["args"]["_newDebt"]

            if creditor < debtor:
                debts[debtor][creditor] = value
            else:
                debts[creditor][debtor] = -value

        return debts

    def unfreeze_network(self):
        unfreeze_call = self.new_network.functions.unFreezeNetwork()
        self.call_contract_function_with_tx(unfreeze_call)
        self.wait_for_successfull_txs_in_queue()

    def remove_owner(self):
        remove_owner_call = self.new_network.functions.removeOwner()
        self.call_contract_function_with_tx(remove_owner_call)
        self.wait_for_successfull_txs_in_queue()

    def call_contract_function_with_tx(self, function_call):
        tx_hash = send_function_call_transaction(
            function_call,
            web3=self.web3,
            transaction_options=self.transaction_options,
            private_key=self.private_key,
        )
        increase_transaction_options_nonce(self.transaction_options)
        self.tx_queue.add(tx_hash)

        if len(self.tx_queue) >= self.max_tx_queue_size:
            self.wait_for_successfull_txs_in_queue()

    def wait_for_successfull_txs_in_queue(self):
        wait_for_successfull_txs(self.web3, self.tx_queue)
        self.tx_queue = set()


class TransactionsFailed(Exception):
    def __init__(self, failed_tx_hashs):
        self.failed_tx_hashs = failed_tx_hashs


def wait_for_successfull_txs(web3, tx_hashs: Iterable[HexBytes], timeout=300):
    # TODO: refactor in deploy tools?

    failed_tx_hashs = set()

    for tx_hash in tx_hashs:
        receipt = web3.eth.waitForTransactionReceipt(tx_hash, timeout=timeout)
        status = receipt.get("status", None)
        if status == 0:
            failed_tx_hashs.add(tx_hash)
        elif status == 1:
            continue
        else:
            raise ValueError(
                f"Unexpected value for status in the transaction receipt: {status}"
            )

    if len(failed_tx_hashs) != 0:
        raise TransactionsFailed(failed_tx_hashs)


def send_function_call_transaction(
    function_call, *, web3: Web3, transaction_options: Dict = None, private_key=None
):
    """
    Creates, signs and sends a transaction from a function call (for example created with `contract.functions.foo()`.
    Will either use an account of the node(default), or a local private key(if given) to sign the transaction.
    It will not block until tx is sent

    Returns: The transaction hash
    """
    # TODO: refactor in deploy tools?
    if transaction_options is None:
        transaction_options = {}

    if private_key is not None:
        signed_transaction = _build_and_sign_transaction(
            function_call,
            web3=web3,
            transaction_options=transaction_options,
            private_key=private_key,
        )
        tx_hash = web3.eth.sendRawTransaction(signed_transaction.rawTransaction)

    else:
        _set_from_address(web3, transaction_options)

        tx_hash = function_call.transact(transaction_options)

    return tx_hash
