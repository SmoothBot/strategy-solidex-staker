import pytest
from brownie import config, Contract

fixtures = "token", "whale", "live_vault", "live_strat"
params = [
    pytest.param( # sAMM-USDC/MIM
        "0xbcab7d083Cf6a01e0DdA9ed7F8a02b47d125e682",
        "0xC009BC33201A85800b3593A40a178521a8e60a02",
        "0x7ff7751E0a2cf789A035caE3ab79c27fD6B0D6cD",
        "0x98E9d5B4822F7e6c3a2854D9E511E7e4cD3cb173",
        id="sAMM-USDC/MIM",
    ),
    # pytest.param( # sAMM-USDC/MIM
    #     "0x154eA0E896695824C87985a52230674C2BE7731b", 
    #     "0x6340dd65D9da8E39651229C1ba9F0ee069E7E4f8", 
    #     "0x7ff7751E0a2cf789A035caE3ab79c27fD6B0D6cD",
    #     "",
    #     id="sAMM-USDC/FRAX",
    # ),
]

@pytest.fixture
def gov(accounts):
    yield accounts[0]


@pytest.fixture
def rewards(accounts):
    yield accounts[1]


@pytest.fixture
def whale(request, accounts):
    acc = accounts.at(request.param, force=True)
    yield acc


@pytest.fixture
def token(request, interface):
    yield interface.ERC20(request.param)


@pytest.fixture
def masterchef(interface):
    yield interface.ERC20("0x26E1A0d851CF28E697870e1b7F053B605C8b060F")


@pytest.fixture
def solid(interface):
    yield interface.ERC20("0x888EF71766ca594DED1F0FA3AE64eD2941740A20")


@pytest.fixture
def sex(interface):
    yield interface.ERC20("0xD31Fcd1f7Ba190dBc75354046F6024A9b86014d7")


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
def live_vault(request, pm, gov, rewards, guardian, management, token):
    if (request.param == ''):
        yield ''
    else:
        Vault = pm(config["dependencies"][0]).Vault
        yield Vault.at(request.param)


@pytest.fixture
def live_strat(request, Strategy):
    if (request.param == ''):
        yield ''
    else:
        yield Strategy.at(request.param)


@pytest.fixture
def vault(pm, gov, rewards, guardian, management, token):
    Vault = pm(config["dependencies"][0]).Vault
    vault = Vault.deploy({'from': gov})
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
    gov,
    chain
):                                                                      
    strategy = Strategy.deploy(vault, {'from': strategist})
    strategy.setKeeper(keeper)

    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    chain.sleep(10)
    yield strategy


# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation, token, whale, live_vault, live_strat):
    pass