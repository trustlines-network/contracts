pragma solidity ^0.5.8;

import "../lib/ECDSA.sol";
import "../currency-network/DebtTracking.sol";
import "./ProxyStorage.sol";


contract Identity is ProxyStorage {

    address public owner;
    bool public initialised;

    mapping(bytes32 => bool) private hashUsed;
    uint public lastNonce = 0;
    // Divides the gas price value to allow for finer range of fee price
    uint public gasPriceDivisor = 1000000;

    event TransactionExecution(bytes32 hash, bool status);
    event FeesPaid(uint value, address currencyNetwork);
    event ContractDeploy(address deployed);

    constructor() public {
        // solium-disable-previous-line no-empty-blocks
        // don't do anything here to allow usage of proxy contracts.
    }

    // This contract can receive ether
    function () external payable {}

    function init(address _owner) public {
        require(! initialised, "The contract has already been initialised.");
        owner = _owner;
        initialised = true;
    }

    function executeTransaction(
        address from,
        address payable to,
        uint256 value,
        bytes memory data,
        uint256 baseFee,
        uint256 gasPrice,
        uint256 gasLimit,
        address currencyNetworkOfFees,
        uint256 nonce,
        uint256 timeLimit,
        uint8 operationType,
        bytes memory extraData,
        bytes memory signature
    )
        public
    {
        uint startGas = gasleft();
        require(from == address(this), "The transaction is not meant for this identity contract");

        bytes32 hash = transactionHash(
            from,
            to,
            value,
            data,
            baseFee,
            gasPrice,
            gasLimit,
            currencyNetworkOfFees,
            nonce,
            timeLimit,
            operationType,
            extraData
        );

        require(validateNonce(nonce, hash), "The transaction nonce is invalid");
        require(validateTimeLimit(timeLimit), "The transaction expired");
        require(validateSignature(hash, signature), "The transaction signature is not valid");

        if (nonce == 0) {
            hashUsed[hash] = true; // To prevent replaying this meta transaction
        } else {
            lastNonce++;
        }

        bool status = applyOperation(to, value, data, operationType);
        emit TransactionExecution(hash, status);

        uint256 gasSpent = startGas - gasleft();
        if (gasLimit != 0) {
            require(gasSpent <= gasLimit, "Gas limit too low");
        }

        if ((gasPrice > 0 || baseFee > 0) && status != false) {
            uint256 fees = baseFee + gasSpent * gasPrice / gasPriceDivisor;
            require(fees >= baseFee, "Fees addition overflow");
            DebtTracking debtContract = DebtTracking(currencyNetworkOfFees);
            debtContract.increaseDebt(msg.sender, fees);
            emit FeesPaid(fees, currencyNetworkOfFees);
        }
    }

    function validateNonce(uint nonce, bytes32 hash) public view returns (bool) {
        if (nonce == 0) {
            return !hashUsed[hash];
        } else {
            return lastNonce + 1 == nonce;
        }

    }

    function validateTimeLimit(uint timeLimit) public view returns (bool) {
        if (timeLimit == 0) {
            return true;
        } else {
            return timeLimit <= now;
        }
    }

    function validateSignature(bytes32 hash, bytes memory _signature) public view returns (bool) {
        address signer = ECDSA.recover(hash, _signature);
        return owner == signer;
    }

    function transactionHash(
        address from,
        address to,
        uint256 value,
        bytes memory data,
        uint256 baseFee,
        uint256 gasPrice,
        uint256 gasLimit,
        address currencyNetworkOfFees,
        uint256 nonce,
        uint256 timeLimit,
        uint8 operationType,
        bytes memory extraData
    )
    internal
    pure
    returns (bytes32)
    {
        // we need to hash the `data` field before being able to pack it to hash it together with other fields
        bytes32 hash = keccak256(
            abi.encodePacked(
                byte(0x19),
                byte(0),
                from,
                to,
                value,
                keccak256(data),
                baseFee,
                gasPrice,
                gasLimit,
                currencyNetworkOfFees,
                nonce,
                timeLimit,
                operationType,
                extraData
            ));

        return hash;
    }

    function applyOperation(address to, uint256 value, bytes memory data, uint8 operationType) internal returns (bool status) {
        if (operationType == 0) {
            // regular call
            (status, ) = to.call.value(value)(data); // solium-disable-line
        } else if (operationType == 1) {
            // delegate call
            require(value == 0, "Cannot transfer value with DELEGATECALL");
            (status, ) = to.delegatecall(data);
        } else if (operationType == 2) {
            // regular crate
            address deployed;
            assembly {
                deployed := create(value, add(data, 0x20), mload(data))
            }
            status = (deployed != address(0));
            if (status) {
                emit ContractDeploy(deployed);
            }
        } else if (operationType == 3) {
            // create2
            address deployed;
            assembly {
              deployed := create2(value, add(data, 0x20), mload(data), 0)
            }
            status = (deployed != address(0));
            if (status) {
                emit ContractDeploy(deployed);
            }
        }
    }
}
