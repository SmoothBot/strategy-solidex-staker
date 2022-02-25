// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

interface ChefLike {
    function deposit(address _pool, uint256 _amount) external;

    function getReward(address[] calldata pools) external;

    function withdraw(address _pool, uint256 _amount) external;

    function userBalances(address _user, address _pool)
        external
        view
        returns (uint256 _balance);
}

// These are the core Yearn libraries
import "@yearnvaults/contracts/BaseStrategy.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/math/Math.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

import "./Interfaces/ISolidlyRouter01.sol";

// Import interfaces for many popular DeFi projects, or add your own!
//import "../interfaces/<protocol>/<Interface>.sol";

contract Strategy is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    address public constant masterchef = address(0x26E1A0d851CF28E697870e1b7F053B605C8b060F);
    IERC20 public constant solidex = IERC20(0xD31Fcd1f7Ba190dBc75354046F6024A9b86014d7);
    IERC20 public constant solid = IERC20(0x888EF71766ca594DED1F0FA3AE64eD2941740A20);

    address private constant solidyRouter = address(0xa38cd27185a464914D3046f0AB9d43356B34829D);
    // address private constant sushiswapRouter = address(0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F);
    address private constant weth = address(0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83);

    ISolidlyRouter01 public router = ISolidlyRouter01(solidyRouter);
    IBaseV1Pair pair;
    IERC20 token0;
    IERC20 token1;

    constructor(
        address _vault,
        uint256 _pid
    ) public BaseStrategy(_vault) {
        _initializeStrat();
    }

    // function initialize(
    //     address _vault,
    //     address _strategist,
    //     address _rewards,
    //     address _keeper
    // ) external {
    //     //note: initialise can only be called once. in _initialize in BaseStrategy we have: require(address(want) == address(0), "Strategy already initialized");
    //     _initialize(_vault, _strategist, _rewards, _keeper);
    //     _initializeStrat();
    // }

    function _initializeStrat() internal {
        // You can set these parameters on deployment to whatever you want
        maxReportDelay = 6300;
        profitFactor = 1500;
        debtThreshold = 1_000_000 * 1e18;

        pair = IBaseV1Pair(address(want));
        want.safeApprove(masterchef, uint256(-1));
        solid.safeApprove(address(router), uint256(-1));
        solidex.safeApprove(address(router), uint256(-1));

        (,,,,, address t0, address t1) = pair.metadata();
        token0 = IERC20(t0);
        token1 = IERC20(t1);
    }

    // function cloneStrategy(
    //     address _vault,
    //     address _reward,
    //     address _router,
    //     uint256 _pid
    // ) external returns (address newStrategy) {
    //     newStrategy = this.cloneStrategy(
    //         _vault,
    //         msg.sender,
    //         msg.sender,
    //         msg.sender,
    //         _masterchef,
    //         _reward,
    //         _router,
    //         _pid
    //     );
    // }

    // function cloneStrategy(
    //     address _vault,
    //     address _strategist,
    //     address _rewards,
    //     address _keeper,
    //     address _masterchef,
    //     address _reward,
    //     address _router,
    //     uint256 _pid
    // ) external returns (address newStrategy) {
    //     // Copied from https://github.com/optionality/clone-factory/blob/master/contracts/CloneFactory.sol
    //     bytes20 addressBytes = bytes20(address(this));

    //     assembly {
    //         // EIP-1167 bytecode
    //         let clone_code := mload(0x40)
    //         mstore(
    //             clone_code,
    //             0x3d602d80600a3d3981f3363d3d373d3d3d363d73000000000000000000000000
    //         )
    //         mstore(add(clone_code, 0x14), addressBytes)
    //         mstore(
    //             add(clone_code, 0x28),
    //             0x5af43d82803e903d91602b57fd5bf30000000000000000000000000000000000
    //         )
    //         newStrategy := create(0, clone_code, 0x37)
    //     }

    //     Strategy(newStrategy).initialize(
    //         _vault,
    //         _strategist,
    //         _rewards,
    //         _keeper,
    //         _masterchef,
    //         _reward,
    //         _router,
    //         _pid
    //     );

    //     emit Cloned(newStrategy);
    // }

    // function setRouter(address _router) public onlyAuthorized {
    //     require(
    //         _router == uniswapRouter || _router == sushiswapRouter,
    //         "incorrect router"
    //     );

    //     router = _router;
    //     IERC20(reward).safeApprove(router, 0);
    //     IERC20(reward).safeApprove(router, uint256(-1));
    // }

    // function setPath(address[] calldata _path) public onlyGovernance {
    //     path = _path;
    // }

    // ******** OVERRIDE THESE METHODS FROM BASE CONTRACT ************

    function name() external view override returns (string memory) {
        return "StrategySolidexStaker";
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        uint256 deposited = ChefLike(masterchef).userBalances(address(this), address(want));
        return want.balanceOf(address(this)).add(deposited);
    }

    function prepareReturn(uint256 _debtOutstanding)
        internal
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        )
    {
        address[] memory pools = new address[](1);
        pools[0] = address(want);
        ChefLike(masterchef).getReward(pools);

        _sell();

        uint256 assets = estimatedTotalAssets();
        uint256 wantBal = want.balanceOf(address(this));

        uint256 debt = vault.strategies(address(this)).totalDebt;

        if (assets >= debt) {
            _profit = assets.sub(debt);
        } else {
            _loss = debt.sub(assets);
        }

        _debtPayment = _debtOutstanding;
        uint256 amountToFree = _debtPayment.add(_profit);

        if (amountToFree > 0 && wantBal < amountToFree) {
            liquidatePosition(amountToFree.sub(wantBal));

            uint256 newLoose = want.balanceOf(address(this));

            // if we didnt free enough money, prioritize paying down debt before taking profit
            if (newLoose < amountToFree) {
                if (newLoose <= _debtPayment) {
                    _profit = 0;
                    _debtPayment = newLoose;
                } else {
                    _profit = newLoose.sub(_debtPayment);
                }
            }
        }
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        if (emergencyExit) {
            return;
        }

        uint256 wantBalance = want.balanceOf(address(this));
        if (wantBalance > 0) {
            ChefLike(masterchef).deposit(address(want), wantBalance);
        }
    }

    function liquidatePosition(uint256 _amountNeeded)
        internal
        override
        returns (uint256 _liquidatedAmount, uint256 _loss)
    {
        uint256 totalAssets = want.balanceOf(address(this));
        if (_amountNeeded > totalAssets) {
            uint256 amountToFree = _amountNeeded.sub(totalAssets);

            uint256 deposited = ChefLike(masterchef).userBalances(address(this), address(want));
            if (deposited < amountToFree) {
                amountToFree = deposited;
            }
            if (deposited > 0) {
                ChefLike(masterchef).withdraw(address(want), amountToFree);
            }

            _liquidatedAmount = want.balanceOf(address(this));
        } else {
            _liquidatedAmount = _amountNeeded;
        }
    }

    // NOTE: Can override `tendTrigger` and `harvestTrigger` if necessary

    function prepareMigration(address _newStrategy) internal override {
        liquidatePosition(uint256(-1)); //withdraw all. does not matter if we ask for too much
        _sell();
    }

    function emergencyWithdrawal(uint256 _pid) external onlyGovernance {
        // uint256 deposited = ChefLike(masterchef).userBalances(address(this), address(want));
        // ChefLike(masterchef).withdraw(address(want), deposited);
    }

    function getTokenOutPath(address _token_in, address _token_out)
        internal
        view
        returns (address[] memory _path)
    {
        bool is_weth =
            _token_in == address(weth) || _token_out == address(weth);
        _path = new address[](is_weth ? 2 : 3);
        _path[0] = _token_in;
        if (is_weth) {
            _path[1] = _token_out;
        } else {
            _path[1] = address(weth);
            _path[2] = _token_out;
        }
    }

    event Log(uint256 indexed solidexBal);
    //sell all function
    function _sell() internal {
        uint256 solidexBal = solidex.balanceOf(address(this));
        emit Log(solidexBal);

        if (solidexBal != 0) {
            router.swapExactTokensForTokensSimple(
                solidexBal,
                uint256(0),
                address(solidex),
                address(token0),
                false,
                address(this),
                now
            );
        }

        uint256 solidBal = solid.balanceOf(address(this));
        if (solidBal != 0) {
            router.swapExactTokensForTokensSimple(
                solidBal,
                uint256(0),
                address(solid),
                address(token0),
                false,
                address(this),
                now
            );
        }

        uint token0Bal = token0.balanceOf(address(this));
        if (token0Bal > 0) {
            router.addLiquidity(
                address(token0),
                address(token1),
                true,
                token0Bal,
                uint(0),
                uint(0),
                uint(0),
                address(this),
                now
            );
        }

    }

    function protectedTokens()
        internal
        view
        override
        returns (address[] memory)
    {}

    function ethToWant(uint256 _amtInWei)
        public
        view
        virtual
        override
        returns (uint256)
    {
        // TODO
        return 0;
    }

    function liquidateAllPositions()
        internal
        override
        returns (uint256 _amountFreed)
    {
        uint256 deposited = ChefLike(masterchef).userBalances(address(this), address(want));
        ChefLike(masterchef).withdraw(address(want), deposited);
        _amountFreed = want.balanceOf(address(this));
    }
}
