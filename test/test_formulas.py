import pytest

from datetime import timedelta
import math

import nomanssky as nms
from nomanssky._formula import (
    Ingredient,
    FormulaType,
    Formula,
    RefineryJob,
    RefineryJobQueue,
    RefineryPool,
    ProductionStage,
    ProductionChain,
)

"""
`(Faecium x1 + Pugneum x1)=Gold x2` -> 
`(Emeril x2 + Gold x2 + Silver x2)=Chromatic_Metal x40` -> 
`(Chromatic_Metal x40 + Sulphurine x40)=Radon x40` -> 
`(Radon x40 + Uranium x40)=Gamma_Root x40` -> 
`(Gamma_Root x40 + Salt x20)=Uranium x20` -> 
`(Pure_Ferrite x10 + Uranium x20)=Pyrite x10` -> 
`(Oxygen x5 + Pyrite x10)=Cactus_Flesh x5` -> 
`(Cactus_Flesh x5 + Condensed_Carbon x5 + Kelp_Sac x5)=Oxygen x50` -> 
`(Nitrogen x50 + Oxygen x50)=Sulphurine x50` -> 
`(Nitrogen x50 + Sulphurine x50)=Faecium x50`
"""

JSON_FORMULAS = Formula.load_list(
    """[
   {"id": 277512525, "type": "{R}", "result": ["Gold", 2], "ingredients": [["Faecium", 1], ["Pugneum", 1]], "process": "Pugneum Alchemy", "time": 0.36},
   {"id": 277517857, "type": "{R}", "result": ["Chromatic_Metal", 20], "ingredients": [["Emeril", 1], ["Gold", 1], ["Silver", 1]], "process": "Chromatic Stellar Fusion", "time": 4.8},
   {"id": 277498261, "type": "{R}", "result": ["Sulphurine", 1], "ingredients": [["Nitrogen", 1], ["Oxygen", 1]], "process": "Gas Transfer", "time": 0.36},
   {"id": 277502429, "type": "{R}", "result": ["Faecium", 1], "ingredients": [["Nitrogen", 1], ["Sulphurine", 1]], "process": "Encourage Growth", "time": 0.24},
   {"id": 277504389, "type": "{R}", "result": ["Cactus_Flesh", 1], "ingredients": [["Oxygen", 1], ["Pyrite", 2]], "process": "Encourage Growth", "time": 0.36},
   {"id": 277504653, "type": "{R}", "result": ["Uranium", 1], "ingredients": [["Gamma_Root", 2], ["Salt", 1]], "process": "Floral Titration", "time": 0.36},
   {"id": 277507609, "type": "{R}", "result": ["Radon", 1], "ingredients": [["Chromatic_Metal", 1], ["Sulphurine", 1]], "process": "Gas Catalysation", "time": 0.36},
   {"id": 277524081, "type": "{R}", "result": ["Oxygen", 10], "ingredients": [["Cactus_Flesh", 1], ["Condensed_Carbon", 1], ["Kelp_Sac", 1]], "process": "Artificial Photosynthesis", "time": 3.6},
   {"id": 277504569, "type": "{R}", "result": ["Gamma_Root", 1], "ingredients": [["Radon", 1], ["Uranium", 1]], "process": "Encourage Growth", "time": 0.24},
   {"id": 275360121, "type": "{R}", "result": ["Pyrite", 1], "ingredients": [["Pure_Ferrite", 1], ["Uranium", 2]], "process": "Environmental Element Transfer", "time": 0.36},
   {"id": 283332933, "type": "{R}", "result": ["Aronium", 1], "ingredients": [["Gold", 10], ["Ionised_Cobalt", 30], ["Paraffinium", 30]], "process": "Alloy Latticing", "time": 45.0},
   {"id": 285109625, "type": "{C}", "result": ["Aronium", 1], "ingredients": [["Ionised_Cobalt", 50], ["Paraffinium", 50]]}
]
"""
)

BY_NAME = {f.result.name: f for f in JSON_FORMULAS}

CHAIN = [
    "Gold",
    "Chromatic_Metal",
    "Radon",
    "Gamma_Root",
    "Uranium",
    "Pyrite",
    "Cactus_Flesh",
    "Oxygen",
    "Sulphurine",
    "Faecium",
]

IN_CHAIN_ORDER = [BY_NAME[id] for id in CHAIN]
ROTATED = IN_CHAIN_ORDER[1:] + IN_CHAIN_ORDER[:1]


@pytest.fixture(scope="module", params=JSON_FORMULAS)
def formula_for_test(request):
    yield request.param


@pytest.fixture(scope="module", params=ROTATED)
def next_formula(request):
    yield request.param


@pytest.fixture(scope="module", params=range(len(IN_CHAIN_ORDER)))
def chain_formulas(request):
    idx = request.param
    yield IN_CHAIN_ORDER[idx], ROTATED[idx]


@pytest.fixture(scope="module", params=[1, 2, 3, 10, 20, 100, 10000])
def multiple(request):
    yield request.param


@pytest.fixture(scope="module", params=[1, 2, 3, 5, 10])
def pool_size(request):
    yield request.param


def test_multiplication(formula_for_test, multiple):
    mul = formula_for_test * multiple
    assert mul.result.name == formula_for_test.result.name
    assert mul.result.qty == formula_for_test.result.qty * multiple
    for i in mul.ingredients:
        assert i.qty == formula_for_test[i.name].qty * multiple


def test_sum_with_self(formula_for_test):
    sum = formula_for_test + formula_for_test

    # print(f"{formula_for_test:'('%ing(', ')')' -> '('%res')'} {sum!r} {sum * 10}")

    assert isinstance(sum, ProductionStage)
    assert len(sum.results) == 1
    assert sum.results[0].name == formula_for_test.result.name
    assert sum.results[0].qty == formula_for_test.result.qty * 2
    assert len(sum.ingredients) == len(formula_for_test.ingredients)
    for i, si in enumerate(sum.ingredients):
        assert si.name == formula_for_test.ingredients[i].name
        assert si.qty == formula_for_test.ingredients[i].qty * 2


def test_sum_with_other(chain_formulas):
    f0 = chain_formulas[0]
    f1 = chain_formulas[1]
    sum = f0 + f1

    print(f"{f0:stage} + {f1:stage} => {sum!r}")
    assert f0.result in sum.results
    assert f1.result in sum.results

    for i0 in f0.ingredients:
        assert i0 in sum

    for i1 in f1.ingredients:
        assert i1 in sum


def test_estimate_time(formula_for_test, multiple):
    big_out = formula_for_test * multiple
    output_batch_size = 4095
    craft_time = 1.0

    (total_time, max_batch_time, batch_count, ref_size) = big_out.estimate_time(
        output_batch_size, craft_time=craft_time
    )
    print(
        f"{big_out:stage} total: {total_time} per batch {max_batch_time} batches {batch_count} {ref_size.name}"
    )

    if formula_for_test.type != FormulaType.CRAFT:
        assert total_time == timedelta(seconds=(formula_for_test.time * multiple))
        assert batch_count == math.ceil(big_out.result.qty / output_batch_size)
    else:
        assert total_time == timedelta(seconds=craft_time * big_out.result.qty)
        assert batch_count == 1
        assert ref_size == nms.RefinerySize.Craft


def test_refinery_queue(multiple):
    queue = RefineryJobQueue()
    proc_time = timedelta(seconds=10)
    for i in range(0, multiple):
        queue.add_job(RefineryJob(None, proc_time, 1))

    assert queue.total_time == proc_time * multiple


def test_unlimited_refinery_pool(multiple):
    pool = RefineryPool(None)
    proc_time = timedelta(seconds=10)

    assert pool.unlimited
    for i in range(0, multiple):
        pool.add_job(RefineryJob(None, proc_time, 1))

    assert pool.max_time == proc_time
    assert pool.actual_pool_size == multiple


def test_single_queue_refinery_pool(multiple):
    pool = RefineryPool()
    proc_time = timedelta(seconds=10)

    assert not pool.unlimited
    assert pool.pool_size == 1

    for i in range(0, multiple):
        pool.add_job(RefineryJob(None, proc_time, 1))

    assert pool.max_time == proc_time * multiple
    assert pool.actual_pool_size == 1


def test_limited_refinery_pool(pool_size, multiple):
    pool = RefineryPool(pool_size)
    proc_time = timedelta(seconds=10)

    assert not pool.unlimited
    assert pool.pool_size == pool_size

    for i in range(0, multiple):
        pool.add_job(RefineryJob(None, proc_time, 1))

    assert pool.actual_pool_size <= pool_size
    assert pool.max_time <= proc_time * multiple


def test_production_chain_create(chain_formulas):
    f0 = chain_formulas[0]
    f1 = chain_formulas[1]
    chain = ProductionChain.from_formula_chain(*chain_formulas)
    print(f"{f0:stage} {f1:stage}")
    print(f"{chain}")
    for s in chain.stages:
        print(f"  {s}")

    print(chain.input)
    print(chain.output)
    print(chain.profit)


def test_big_chain():
    chain = ProductionChain.from_formula_chain(*IN_CHAIN_ORDER)
    print(f"{chain}")
    for s in chain.stages:
        print(f"  {s}")

    print(chain.input)
    print(chain.output)
    print(chain.profit)
    print(chain)
