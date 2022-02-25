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
    acc = accounts.at("0xC009BC33201A85800b3593A40a178521a8e60a02", force=True)
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
def pool(interface, token):
    yield interface.IBaseV1Pair(token.address)


# underlying tokens of LP
@pytest.fixture
def tokens(interface, pool):
    meta = pool.metadata()
    yield [interface.ERC20(meta[5]), interface.ERC20(meta[6])]
    

# Assumes tokens are each ~$1 -> only works for USDC stables
@pytest.fixture
def price(pool, token, tokens):
    res = pool.getReserves()
    sum = res[0] / (10 ** tokens[0].decimals()) + res[1] / (10 ** tokens[1].decimals())
    yield sum / (token.totalSupply() / 1e18)

    
@pytest.fixture
def decimals(token):
    yield token.decimals()

@pytest.fixture
def amount(price):
    amount = int(1_000_000 * 1e18 / price)
    yield amount


@pytest.fixture
def weth():
    token_address = "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83"
    yield Contract(token_address)


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
    vault.initialize(token, gov, rewards, "", "", guardian, {'from': gov})
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagement(management, {"from": gov})
    yield vault


@pytest.fixture
def strategy(
    strategist,
    keeper,
    vault,
    Strategy,
    gov
):
    strategy = strategist.deploy(Strategy, vault)
    strategy.setKeeper(keeper)

    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    yield strategy

# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation):
    pass