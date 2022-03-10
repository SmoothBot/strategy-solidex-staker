import brownie
from brownie import Contract
from useful_methods import genericStateOfVault, genericStateOfStrat
import random
import pytest
import conftest as config


@pytest.mark.parametrize(config.fixtures, config.params, indirect=True)
def test_apr(accounts, token, vault, strategy, chain, strategist, amount, whale):
    strategist = accounts[0]

    print(token.address)

    # Deposit to the vault
    token.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount

    # harvest
    strategy.harvest()
    startingBalance = vault.totalAssets()
    for i in range(2):

        waitBlock = 50
        # print(f'\n----wait {waitBlock} blocks----')
        chain.mine(waitBlock)
        chain.sleep(waitBlock * 13)
        # print(f'\n----harvest----')
        strategy.harvest({"from": strategist})

        genericStateOfStrat(strategy, token, vault)
        genericStateOfVault(vault, token)

        profit = (vault.totalAssets() - startingBalance) / 1e18
        strState = vault.strategies(strategy)
        totalReturns = strState[7]
        totaleth = totalReturns / 1e18
        print(f'Real Profit: {profit:.5f}')
        difff = profit - totaleth
        print(f'Diff: {difff}')

        blocks_per_year = 2_252_857
        assert startingBalance != 0
        time = (i + 1) * waitBlock
        assert time != 0
        apr = (totalReturns / startingBalance) * (blocks_per_year / time)
        assert apr > 0
        # print(apr)
        print(f"implied apr: {apr:.8%}")


@pytest.mark.parametrize(config.fixtures, config.params, indirect=True)
def test_profitable_harvest(accounts, token, vault, strategy, strategist, whale, chain, price, amount):

    bbefore = token.balanceOf(whale)

    # Deposit to the vault
    token.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount

    # harvest
    strategy.harvest()
    for i in range(15):
        waitBlock = random.randint(100, 500)
        chain.sleep(waitBlock)

    chain.mine(1)
    strategy.harvest()
    chain.sleep(60000)
    # withdrawal
    vault.withdraw({"from": whale})
    assert token.balanceOf(whale) > bbefore
    genericStateOfStrat(strategy, token, vault)
    genericStateOfVault(vault, token)


@pytest.mark.parametrize(config.fixtures, config.params, indirect=True)
def test_profitable_harvest_w_solidly_sell(accounts, token, vault, strategy, strategist, whale, chain, price, amount):

    bbefore = token.balanceOf(whale)

    # Deposit to the vault
    token.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount
    
    strategy.setUseSpookyToSellSolid(False, {'from':strategist})
    # harvest
    strategy.harvest()
    for i in range(15):
        waitBlock = random.randint(10, 50)
        chain.sleep(waitBlock)

    chain.mine(1)
    strategy.harvest()
    chain.sleep(60000)
    # withdrawal
    vault.withdraw({"from": whale})
    assert token.balanceOf(whale) > bbefore
    genericStateOfStrat(strategy, token, vault)
    genericStateOfVault(vault, token)


@pytest.mark.parametrize(config.fixtures, config.params, indirect=True)
def test_emergency_withdraw(
    accounts, token, vault, strategy, strategist, whale, chain, gov
):
    amount = 1 * 1e18
    bbefore = token.balanceOf(whale)

    # Deposit to the vault
    token.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount

    # harvest deposit into staking contract
    strategy.harvest()
    assert token.balanceOf(strategy) == 0
    strategy.emergencyWithdrawalAll({"from": gov})
    assert token.balanceOf(strategy) >= amount


@pytest.mark.parametrize(config.fixtures, config.params, indirect=True)
def test_emergency_exit(chain, token, vault, strategy, strategist, amount, whale, decimals):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    strategy.harvest()
    assert strategy.estimatedTotalAssets() == amount
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-4) == amount

    # set emergency and exit
    chain.sleep(1)
    strategy.setEmergencyExit()
    strategy.harvest()
    dust = (1e-5 * 10 ** decimals)
    assert strategy.estimatedTotalAssets() < dust


@pytest.mark.parametrize(config.fixtures, config.params, indirect=True)
def test_change_debt(chain, gov, token, vault, strategy, strategist, amount, whale, decimals):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})

    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()
    chain.sleep(10)
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-5) == amount / 2

    vault.updateStrategyDebtRatio(strategy.address, 10_000, {"from": gov})
    strategy.harvest()
    chain.sleep(10)
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-5) == amount

    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()
    chain.sleep(10)
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-5) == amount / 2

    vault.updateStrategyDebtRatio(strategy.address, 0, {"from": gov})
    strategy.harvest()
    dust = (1e-5 * 10 ** decimals)
    assert strategy.estimatedTotalAssets() < dust


@pytest.mark.parametrize(config.fixtures, config.params, indirect=True)
def test_sweep(gov, vault, strategy, token, amount, whale):
    # Strategy want token doesn't work
    token.transfer(strategy, amount, {"from": whale})
    assert token.address == strategy.want()
    assert token.balanceOf(strategy) > 0
    with brownie.reverts("!want"):
        strategy.sweep(token, {"from": gov})

    # Vault share token doesn't work
    with brownie.reverts("!shares"):
        strategy.sweep(vault.address, {"from": gov})


@pytest.mark.parametrize(config.fixtures, config.params, indirect=True)
def test_triggers(gov, vault, strategy, token, amount, whale):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()

    strategy.harvestTrigger(1)
    strategy.tendTrigger(1)
