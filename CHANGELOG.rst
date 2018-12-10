==========
Change Log
==========
`0.4.0`_ (2018-12-10)
-----------------------
* Remove the fees on the last hop

  A user now only has to pay fees to the true mediators and not anymore to the receiver.
  
* Add transfer function where receiver pays the fees

  It is now possible to make payments, where the receiver will pay the fees.

* Round up fees

  We are now properly rounding up the fees, where before we used an own formular that was 
  already close to rounding up.

* Bug Fix #159
  that an old trustline request could be accepted

`0.3.3`_ (2018-11-28)
-----------------------
* Bug fix deploy tool so that it is possible to deploy a network with zero fees
* First version of trustlines-contracts-abi on npm. 
  
`0.3.2`_ (2018-11-26)
-----------------------
* Optimize gas cost of contracts
  
`0.3.1`_ (2018-11-13)
-----------------------
* Fix a dependency issue  
  
`0.3.0`_ (2018-11-12)
-----------------------
* Added interests to currency networks

  A trustline now also consists of two interest rates given by the two parties to each other.
  These interest rates are used to calculate occured interests between the two parties. The balance
  including the interests is updated whenever the balance (because of a transfer) or one of
  the interest rates (because of a trustline update) changes. To calculate the interests we
  approximate Continuous Compounding with a taylor series and use the current timestamp and
  the timestamp of the last update.

* Added interest settings to deploy tool

  The deploy tool now allows deploying networks with different interests settings. The current options
  are: Default interests: If this is set, every trustline has the same interest rate.
  Custom interest: If this is set, every user can decide which interest rate he want to give.
  Prevent mediator interests: Safe setting to prevent mediators from paying interests for
  mediated transfer by disallowing certain transfers.

* Close a trustline

  Added a new function to do a triangular payment to close a trustline. This will set the balance
  between two user to zero and also removes all information about this trustline. This is still work
  in progress and might change.

`0.2.0`_ (2018-09-19)
-----------------------
* the python package `trustlines-contracts` is now superseded by the
  trustlines-contracts-deploy package. The old namespace tlcontracts is gone.
  The python code now lives in the tldeploy package. The tl-deploy script should
  work as before, but the installation got a lot easier (i.e. just pip install
  trustlines-contracts-deploy)

The rest of the changes are only interesting for developers:

* the internal tests do not rely on populus being installed. populus isn't a
  dependency of trustlines-contracts-deploy anymore.
* populus is still needed for smart contract compilation. It's being installed
  to a local virtualenv automatically by the newly introduced Makefile.
* The field capacityImbalanceFeeDivisor was made public. As a result, there's
  now a getter function for it in the ABI.

`0.1.3`_ (2018-09-04)
---------------------
* trustlines-contracts-deploy has been released to PyPI

`0.1.2`_ (2018-08-21)
---------------------
* trustlines-contracts has also been released to PyPI

`0.1.1`_ (2018-08-20)
---------------------
* trustlines-contracts-bin has been released to PyPI


.. _0.1.1: https://github.com/trustlines-network/contracts/compare/0.1.0...0.1.1
.. _0.1.2: https://github.com/trustlines-network/contracts/compare/0.1.1...0.1.2
.. _0.1.3: https://github.com/trustlines-network/contracts/compare/0.1.2...0.1.3
.. _0.2.0: https://github.com/trustlines-network/contracts/compare/0.1.3...0.2.0
.. _0.3.0: https://github.com/trustlines-network/contracts/compare/0.2.0...0.3.0
.. _0.3.1: https://github.com/trustlines-network/contracts/compare/0.3.0...0.3.1
.. _0.3.2: https://github.com/trustlines-network/contracts/compare/0.3.1...0.3.2
.. _0.3.3: https://github.com/trustlines-network/contracts/compare/0.3.2...0.3.3
.. _0.4.0: https://github.com/trustlines-network/contracts/compare/0.3.3...0.4.0
