import pytest
from brownie import config, Contract


@pytest.fixture
def gov(accounts):
    yield accounts[0]


@pytest.fixture
def rewards(accounts):
    yield accounts[1]


@pytest.fixture
def whale(accounts):
    # big binance7 wallet
    # acc = accounts.at('0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8', force=True)
    # big binance8 wallet
    acc = accounts.at("0xC009BC33201A85800b3593A40a178521a8e60a02", force=True)

    # lots of weth account
    # wethAcc = accounts.at("0x767Ecb395def19Ab8d1b2FCc89B3DDfBeD28fD6b", force=True)
    # weth.approve(acc, 2 ** 256 - 1, {"from": wethAcc})
    # weth.transfer(acc, weth.balanceOf(wethAcc), {"from": wethAcc})

    # assert weth.balanceOf(acc) > 0
    yield acc

@pytest.fixture
def masterchef(interface):
    yield interface.ERC20("0x26E1A0d851CF28E697870e1b7F053B605C8b060F")

# @pytest.fixture
# def solid(interface):
#     yield interface.ERC20("0x888EF71766ca594DED1F0FA3AE64eD2941740A20")

# @pytest.fixture
# def sex(interface):
#     yield interface.ERC20("0xD31Fcd1f7Ba190dBc75354046F6024A9b86014d7")


@pytest.fixture
def guardian(accounts):
    yield accounts[2]


@pytest.fixture
def management(accounts):
    yield accounts[3]


@pytest.fixture
def strategist(accounts):
    yield accounts[4]


@pytest.fixture
def keeper(accounts):
    yield accounts[5]


@pytest.fixture
def token(interface):
    yield interface.ERC20('0xbcab7d083Cf6a01e0DdA9ed7F8a02b47d125e682') # sAMM-USDC/MIM


@pytest.fixture
def amount(accounts, token):
    amount = 10_000 * 10 ** token.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    reserve = accounts.at("0xd551234ae421e3bcba99a0da6d736074f22192ff", force=True)
    token.transfer(accounts[0], amount, {"from": reserve})
    yield amount


@pytest.fixture
def weth():
    token_address = "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83"
    yield Contract(token_address)


@pytest.fixture
def weth_amount(gov, weth):
    weth_amount = 10 ** weth.decimals()
    gov.transfer(weth, weth_amount)
    yield weth_amount


@pytest.fixture
def live_vault(pm, gov, rewards, guardian, management, token):
    Vault = pm(config["dependencies"][0]).Vault
    yield Vault.at("0xE14d13d8B3b85aF791b2AADD661cDBd5E6097Db1")


@pytest.fixture
def live_strat(Strategy):
    yield Strategy.at("0xd4419DDc50170CB2DBb0c5B4bBB6141F3bCc923B")


@pytest.fixture
def live_vault_weth(pm, gov, rewards, guardian, management, token):
    Vault = pm(config["dependencies"][0]).Vault
    yield Vault.at("0xa9fE4601811213c340e850ea305481afF02f5b28")


@pytest.fixture
def live_strat_weth(Strategy):
    yield Strategy.at("0xDdf11AEB5Ce1E91CF19C7E2374B0F7A88803eF36")


@pytest.fixture
def vault(pm, gov, rewards, guardian, management, token):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(token, gov, rewards, "", "", guardian)
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagement(management, {"from": gov})
    yield vault


@pytest.fixture
def strategy(
    strategist,
    keeper,
    vault,
    token,
    weth,
    Strategy,
    gov
):
    strategy = strategist.deploy(Strategy, vault, token.address)
    strategy.setKeeper(keeper)

    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    yield strategy
