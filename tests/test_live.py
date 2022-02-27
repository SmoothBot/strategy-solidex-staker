import brownie
from brownie import Contract
from useful_methods import genericStateOfVault, genericStateOfStrat
import random


def test_migrate_live(
    accounts,
    Strategy,
    token,
    live_vault,
    live_strat,
    chain,
    strategist
):
    gov = accounts.at(live_vault.governance(), force=True)
    strategist = gov
    strategy = live_strat
    vault = live_vault

    before = strategy.estimatedTotalAssets()

    new_strategy = Strategy.deploy(vault, {'from': strategist})

    # migrate to a new strategy
    vault.migrateStrategy(strategy, new_strategy, {"from": gov})

    assert new_strategy.estimatedTotalAssets() >= before
    assert strategy.estimatedTotalAssets() == 0


def test_apr_live(accounts, Strategy, token, live_vault, live_strat, chain, strategist, whale):
    gov = accounts.at(live_vault.governance(), force=True)
    strategist = gov
    vault = live_vault

    strategy = Strategy.deploy(vault, {'from': strategist})

    # migrate to a new strategy
    ppsBefore = vault.pricePerShare()
    vault.migrateStrategy(live_strat, strategy, {"from": gov})
    assert vault.pricePerShare() >= ppsBefore

    strategy.harvest({"from": gov})

    # genericStateOfStrat(strategy, token, vault)
    # genericStateOfVault(vault, token)
    strState = vault.strategies(strategy)
    startingBalance = vault.totalAssets()
    startingReturns = strState[7]
    for i in range(1):

        waitBlock = 50
        # print(f'\n----wait {waitBlock} blocks----')
        chain.mine(waitBlock)
        chain.sleep(waitBlock * 13)
        # print(f'\n----harvest----')
        strategy.harvest({"from": strategist})

        # genericStateOfStrat(strategy, currency, vault)
        # genericStateOfVault(vault, currency)

        profit = (vault.totalAssets() - startingBalance) / 1e18
        strState = vault.strategies(strategy)
        totalReturns = strState[7] - startingReturns
        totaleth = totalReturns / 1e18
        # print(f'Real Profit: {profit:.5f}')
        difff = profit - totaleth
        # print(f'Diff: {difff}')

        blocks_per_year = 2_252_857
        assert startingBalance != 0
        time = (i + 1) * waitBlock
        assert time != 0
        apr = (totalReturns / startingBalance) * (blocks_per_year / time)
        assert apr > 0
        # print(apr)
        print(f"implied apr: {apr:.8%}")

    dust = 1e10
    vault.revokeStrategy(strategy, {"from": gov})
    strategy.harvest({"from": gov})
    assert strategy.estimatedTotalAssets() <= dust
    # genericStateOfStrat(strategy, token, vault)
    # genericStateOfVault(vault, token)
