// SPDX-License-Identifier: MIT
pragma experimental ABIEncoderV2;
pragma solidity 0.6.12;

interface IOxLens {
    function oxPoolBySolidPool(address solidPoolAddress)
        external
        view
        returns (address);
}