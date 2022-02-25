import brownie
from brownie import Contract

# TODO: Add tests that show proper migration of the strategy to a newer one
#       Use another copy of the strategy to simulate the migration
#       Show that nothing is lost!


def test_migration(
    token,
    vault,
    chain,
    strategy,
    Strategy,
    strategist,
    whale,
    gov,
    bdp_masterchef,
    bdp,
    router,
    pid,
    amount
):

    # Deposit to the vault and harvest
    bbefore = token.balanceOf(whale)

    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    strategy.harvest()

    tx = strategy.cloneStrategy(vault, bdp_masterchef, bdp, router, pid)

    # migrate to a new strategy
    new_strategy = Strategy.at(tx.return_value)

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
