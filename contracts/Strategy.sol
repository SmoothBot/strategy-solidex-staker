// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

struct Amounts {
    uint256 solid;
    uint256 sex;
}

interface ChefLike {

    function deposit(address _pool, uint256 _amount) external;

    function getReward(address[] calldata pools) external;

    function withdraw(address _pool, uint256 _amount) external;

    function userBalances(address _user, address _pool)
        external
        view
        returns (uint256 _balance);

    function pendingRewards(address _user, address[] calldata pools)
        external
        view
        returns (Amounts[] memory pending);
}

// These are the core Yearn libraries
import "@yearnvaults/contracts/BaseStrategy.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/math/Math.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

import "./Interfaces/ISolidlyRouter01.sol";
import "./Interfaces/UniswapInterfaces/IUniswapV2Router01.sol";

contract Strategy is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    /*///////////////////////////////////////////////////////////////
                               IMMUTABLES
    //////////////////////////////////////////////////////////////*/

    uint constant BPS = 10000;
    address public constant masterchef = address(0x26E1A0d851CF28E697870e1b7F053B605C8b060F);
    IERC20 public constant solidex = IERC20(0xD31Fcd1f7Ba190dBc75354046F6024A9b86014d7);
    IERC20 public constant solid = IERC20(0x888EF71766ca594DED1F0FA3AE64eD2941740A20);
    address public constant weth = address(0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83);

    ISolidlyRouter01 public router = ISolidlyRouter01(0xa38cd27185a464914D3046f0AB9d43356B34829D);
    IUniswapV2Router01 public spookyRouter = IUniswapV2Router01(0xF491e7B69E4244ad4002BC14e878a34207E38c29);
    IBaseV1Pair pair;
    IERC20 public token0;
    IERC20 public token1;
    address[] private pools = new address[](1);
    

    /*///////////////////////////////////////////////////////////////
                              CONSTRUCTOR
    //////////////////////////////////////////////////////////////*/
    constructor(
        address _vault
    ) public BaseStrategy(_vault) {
        // You can set these parameters on deployment to whatever you want
        maxReportDelay = 6300;
        profitFactor = 1500;
        debtThreshold = 1_000_000 * 1e18;

        pair = IBaseV1Pair(address(want));

        (,,,,, address t0, address t1) = pair.metadata();
        token0 = IERC20(t0);
        token1 = IERC20(t1);
        pools[0] = address(want);

        want.safeApprove(masterchef, uint256(-1));
        solid.safeApprove(address(router), uint256(-1));
        solid.safeApprove(address(spookyRouter), uint256(-1));
        solidex.safeApprove(address(router), uint256(-1));
        token0.safeApprove(address(router), uint256(-1));
        token1.safeApprove(address(router), uint256(-1));
    }

    /*///////////////////////////////////////////////////////////////
                      SLIPPAGE OFFSET CONFIGURATION
    //////////////////////////////////////////////////////////////*/

    /// @notice determines how token0 is split when adding to LP
    uint256 public slippageOffset = 50;

    /// @notice Update the Slippage Offset.
    /// @param _slippageOffset The new Slippage Offset.
    function setSlippageOffset(uint256 _slippageOffset) external onlyAuthorized {
        slippageOffset = _slippageOffset;
    }

    /*///////////////////////////////////////////////////////////////
                        MIN LIQUIDITY CONFIGURATION
    //////////////////////////////////////////////////////////////*/

    /// @notice min liquidity of token0 needed to create new LP
    uint256 public minLiquidity = 1e4;

    /// @notice Update the Min Liquidity
    /// @param _minLiquidity The new Min Liquidity
    function setMinLiquidity(uint256 _minLiquidity) external onlyAuthorized {
        minLiquidity = _minLiquidity;
    }

    /*///////////////////////////////////////////////////////////////
                         REWARD DUST CONFIGURATION
    //////////////////////////////////////////////////////////////*/

    /// @notice minimum reward token needed to trigger a sell to token0
    uint256 public rewardDust = 1e12;

    /// @notice Update the Reward Dust
    /// @param _rewardDust The new Reward Dust
    function setRewardDust(uint256 _rewardDust) external onlyAuthorized {
        rewardDust = _rewardDust;
    }

    /*///////////////////////////////////////////////////////////////
                         IGNORE SELL CONFIGURATION
    //////////////////////////////////////////////////////////////*/

    /// @notice determines how token0 is split when adding to LP
    bool public ignoreSell = false;

    /// @notice set to true to ingore the selling of reward tokens and adding lp
    /// @param _ignoreSell The new Slippage Offset.
    function setIgnoreSell(bool _ignoreSell) external onlyAuthorized {
        ignoreSell = _ignoreSell;
    }

    /*///////////////////////////////////////////////////////////////
                        MIN MARVEST CREDIT CONFIGURATION
    //////////////////////////////////////////////////////////////*/

    /// @notice When our strategy has this much credit, harvestTrigger will be true.
    uint256 public minHarvestCredit = type(uint256).max;

    /// @notice Update the Min Harvest Credit
    /// @param _minHarvestCredit The new Min Harvest Credit
    function setMinHarvestCredit(uint256 _minHarvestCredit) external onlyAuthorized {
        minHarvestCredit = _minHarvestCredit;
    }

    /*///////////////////////////////////////////////////////////////
                         USE SPOOKY CONFIGURATION
    //////////////////////////////////////////////////////////////*/

    /// @notice Set to true to use the spooky router instead of solidly for selling solid
    bool public useSpookyToSellSolid = true;

    /// @notice set useSpookyToSellSolid
    /// @param _useSpookyToSellSolid The new useSpookyToSellSolid setting
    function setUseSpookyToSellSolid(bool _useSpookyToSellSolid) external onlyAuthorized {
        useSpookyToSellSolid = _useSpookyToSellSolid;
    }

    // ******** OVERRIDE THESE METHODS FROM BASE CONTRACT ************

    function name() external view override returns (string memory) {
        return "StrategySolidexStaker";
    }

    function balanceOfWant() public view returns (uint256) {
        return want.balanceOf(address(this));
    }

    function balanceOfStaked() public view returns (uint256) {
        return ChefLike(masterchef).userBalances(address(this), address(want));
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        // look at our staked tokens and any free tokens sitting in the strategy
        return balanceOfStaked().add(balanceOfWant());
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

        if (_doClaim()) {
            ChefLike(masterchef).getReward(pools);
        }

        _sell();

        uint256 assets = estimatedTotalAssets();
        uint256 wantBal = want.balanceOf(address(this));

        uint256 debt = vault.strategies(address(this)).totalDebt;

        _debtPayment = _debtOutstanding;
        uint256 amountToFree = _debtPayment.add(_profit);

        if (assets >= debt) {
            _debtPayment = _debtOutstanding;
            _profit = assets - debt;

            amountToFree = _profit.add(_debtPayment);

            if (amountToFree > 0 && wantBal < amountToFree) {
                liquidatePosition(amountToFree);

                uint256 newLoose = want.balanceOf(address(this));

                //if we dont have enough money adjust _debtOutstanding and only change profit if needed
                if (newLoose < amountToFree) {
                    if (_profit > newLoose) {
                        _profit = newLoose;
                        _debtPayment = 0;
                    } else {
                        _debtPayment = Math.min(
                            newLoose - _profit,
                            _debtPayment
                        );
                    }
                }
            }
        } else {
            //serious loss should never happen but if it does lets record it accurately
            _loss = debt - assets;
        }
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        if (emergencyExit) {
            return;
        }

        uint256 wantBalance = want.balanceOf(address(this));
        if (wantBalance > 1e6) {
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

    function prepareMigration(address _newStrategy) internal override {
        liquidatePosition(uint256(-1)); //withdraw all. does not matter if we ask for too much
        _sell();
    }

    function emergencyWithdrawal(uint256 _amount) external onlyGovernance {
        ChefLike(masterchef).withdraw(address(want), _amount);
    }

    function emergencyWithdrawalAll() external onlyGovernance {
        uint256 deposited = ChefLike(masterchef).userBalances(address(this), address(want));
        ChefLike(masterchef).withdraw(address(want), deposited);
    }

    function _doClaim() internal view returns (bool) {
        Amounts[] memory pending = ChefLike(masterchef).pendingRewards(address(this), pools);
        return (pending[0].sex > 0 || pending[0].solid > 0);
    }

    function _getTokenOutRoute(address _token_in, address _token_out)
        internal
        view
        returns (Route[] memory _route)
    {
        bool is_weth = _token_in == address(weth) || _token_out == address(weth);
        _route = new Route[](is_weth ? 1 : 2);
        _route[0].from = _token_in;
        if (is_weth) {
            _route[0].to = _token_out;
            _route[0].stable = false;
        } else {
            _route[0].stable = false;
            _route[1].stable = false;
            _route[0].to = address(weth);
            _route[1].from = address(weth);
            _route[1].to = _token_out;
        }
    }

    function _getTokenOutPath(address _token_in, address _token_out)
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

    function manualSell() external onlyAuthorized {
        _sell();
    }

    // Sells reward tokens and created LP
    function _sell() internal {
        if (ignoreSell)
            return;

        uint256 solidexBal = solidex.balanceOf(address(this));
        if (solidexBal > rewardDust) {
            router.swapExactTokensForTokens(
                solidexBal,
                uint256(0),
                _getTokenOutRoute(address(solidex), address(token0)),
                address(this),
                now
            );
        }

        uint256 solidBal = solid.balanceOf(address(this));
        if (solidBal > rewardDust) {
            // TODO - use spooky to sell solid?
            if (useSpookyToSellSolid) {
                spookyRouter.swapExactTokensForTokens(
                    solidBal,
                    uint256(0),
                    _getTokenOutPath(address(solid), address(token0)),
                    address(this),
                    now
                );
            } else {
                router.swapExactTokensForTokens(
                    solidBal,
                    uint256(0),
                    _getTokenOutRoute(address(solid), address(token0)),
                    address(this),
                    now
                );
            }
        }

        uint token0Bal = token0.balanceOf(address(this));
        if (token0Bal > minLiquidity) {
            uint swapAmount;
            if (token1.balanceOf(address(this)) > 0) {
                swapAmount = token0Bal.mul(BPS.sub(slippageOffset)).div(BPS.mul(2));
            } else {
                swapAmount = token0Bal.mul(BPS.add(slippageOffset)).div(BPS.mul(2));
            }

            // Sell 50% - TODO this can be done more accurately
            router.swapExactTokensForTokensSimple(
                swapAmount,
                uint(0),
                address(token0),
                address(token1),
                true,
                address(this),
                now
            );

            router.addLiquidity(
                address(token0),
                address(token1),
                true,
                token0.balanceOf(address(this)),
                token1.balanceOf(address(this)),
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

    function harvestTrigger(uint256 callCostinEth)
        public
        view
        override
        returns (bool)
    {
        // trigger if we have enough credit
        if (vault.creditAvailable() >= minHarvestCredit) {
            return true;
        }

        // otherwise, we don't harvest
        return super.harvestTrigger(callCostinEth);
    }

    function ethToWant(uint256 _amtInWei)
        public
        view
        virtual
        override
        returns (uint256)
    {
        return 0;
    }

    function liquidateAllPositions()
        internal
        override
        returns (uint256 _amountFreed)
    {
        uint256 deposited = ChefLike(masterchef).userBalances(address(this), address(want));
        if (deposited > 0) {
            ChefLike(masterchef).withdraw(address(want), deposited);
        }
        _amountFreed = want.balanceOf(address(this));
    }
}
