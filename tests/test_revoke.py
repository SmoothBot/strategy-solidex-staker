import pytest
import conftest as config

@pytest.mark.parametrize(config.fixtures, config.params, indirect=True)
def test_revoke_strategy_from_vault(token, chain, vault, strategy, amount, gov, whale):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    strategy.harvest()
    assert strategy.estimatedTotalAssets() >= amount

    # Test revokeStrategy
    chain.sleep(10)
    vault.revokeStrategy(strategy.address, {"from": gov})
    strategy.harvest()
    assert token.balanceOf(vault.address) >= amount


@pytest.mark.parametrize(config.fixtures, config.params, indirect=True)
def test_revoke_emergency_exit(token, chain, vault, strategy, amount, gov, whale):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    strategy.harvest()
    assert strategy.estimatedTotalAssets() >= amount

    chain.sleep(10)
    strategy.setEmergencyExit()
    strategy.harvest()
    assert token.balanceOf(vault.address) >= amount
