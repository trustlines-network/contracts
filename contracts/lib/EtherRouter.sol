pragma solidity ^0.4.8;


import "./Resolver.sol";


contract EtherRouter {
    Resolver resolver;

    function constructor(Resolver _resolver) public {
        resolver = _resolver;
    }

    function() public payable {
        uint r;

        // Get routing information for the called function
        var (destination, outsize) = resolver.lookup(msg.sig, msg.data);

        // Make the call
        assembly {
            calldatacopy(mload(0x40), 0, calldatasize)
            r := delegatecall(sub(gas, 700), destination, mload(0x40), calldatasize, mload(0x40), outsize)
        }

        // Throw if the call failed
        if (r != 1) {
            revert();
        }

        // Pass on the return value
        assembly {
            return (mload(0x40), outsize)
        }
    }
}
