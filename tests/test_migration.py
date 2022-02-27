import brownie
from brownie import Contract
import pytest
import conftest as config


@pytest.mark.parametrize(config.fixtures, config.params, indirect=True)
def test_migration(
    token,
    vault,
    chain,
    strategy,
    Strategy,
    strategist,
    whale,
    gov,
    amount
):

    # Deposit to the vault and harvest
    bbefore = token.balanceOf(whale)

    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    strategy.harvest()

    # migrate to a new strategy
    new_strategy = Strategy.deploy(vault, {'from': strategist})

    vault.migrateStrategy(strategy, new_strategy, {"from": gov})
    assert new_strategy.estimatedTotalAssets() >= amount
    assert strategy.estimatedTotalAssets() == 0

    new_strategy.harvest({"from": gov})

    chain.mine(20)
    chain.sleep(2000)
    new_strategy.harvest({"from": gov})
    chain.sleep(60000)
    vault.withdraw({"from": whale})
    assert token.balanceOf(whale) > bbefore
