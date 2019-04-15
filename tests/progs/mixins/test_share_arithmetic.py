from pytest import mark, raises
from asyncio import gather
from honeybadgermpc.progs.mixins.share_arithmetic import (
    BeaverMultiply, BeaverMultiplyArrays, InvertShare, InvertShareArray, DivideShares,
    DivideShareArrays, Equality, DoubleSharingMultiply, DoubleSharingMultiplyArrays)

STANDARD_ARITHMETIC_MIXINS = [
    BeaverMultiply(),
    BeaverMultiplyArrays(),
    InvertShare(),
    InvertShareArray(),
    DivideShares(),
    DivideShareArrays(),
    Equality()
]

STANDARD_PREPROCESSING = [
    'double_shares', 'rands', 'zeros', 'triples', 'bits'
]

n, t = 3, 1


async def run_test_program(prog, test_runner, n=n, t=t, k=10000,
                           mixins=STANDARD_ARITHMETIC_MIXINS):

    return await test_runner(prog, n, t, STANDARD_PREPROCESSING, k, mixins)


@mark.asyncio
async def test_degree_reduction_share(galois_field, test_preprocessing, test_runner):
    n, t = 9, 2
    x_expected = galois_field.random().value
    sid_x_2t = test_preprocessing.generate("share", n, 2*t, x_expected)

    async def _prog(context):
        sh_x_2t = test_preprocessing.elements.get_share(context, sid_x_2t, 2*t)
        x_actual = await (
            await DoubleSharingMultiply.reduce_degree_share(context, sh_x_2t)).open()
        assert x_expected == x_actual

    await run_test_program(_prog, test_runner, n, t)


@mark.asyncio
async def test_degree_reduction_share_array(test_preprocessing, test_runner):
    n, t = 9, 2
    test_preprocessing.generate("rands", n, 2*t)

    async def _prog(context):
        shares = [test_preprocessing.elements.get_rand(context, 2*t) for _ in range(10)]
        sh_x_2t = context.ShareArray(shares, 2*t)
        x_actual = await (
            await DoubleSharingMultiplyArrays.reduce_degree_share_array(
                context, sh_x_2t)).open()

        x_expected = await sh_x_2t.open()
        for a, b in zip(x_actual, x_expected):
            assert a == b

    await run_test_program(_prog, test_runner, n, t)


@mark.asyncio
async def test_multiplication_using_double_sharing(galois_field,
                                                   test_preprocessing,
                                                   test_runner):
    n, t = 9, 2

    async def _prog(context):
        sh_a = test_preprocessing.elements.get_rand(context)
        sh_b = test_preprocessing.elements.get_rand(context)
        ab_expected = await sh_a.open() * await sh_b.open()

        ab_actual = await(await (sh_a * sh_b)).open()
        assert ab_expected == ab_actual

    await run_test_program(_prog, test_runner, n, t)


@mark.asyncio
async def test_batch_double_sharing_multiply(galois_field,
                                             test_preprocessing,
                                             test_runner):
    n, t = 9, 2

    async def _prog(context):
        shares = [test_preprocessing.elements.get_rand(context) for _ in range(20)]
        p = context.ShareArray(shares[:10])
        q = context.ShareArray(shares[10:])

        p_f, q_f = await p.open(), await q.open()
        pq_acutal = await (await (p*q)).open()
        for xy, x, y in zip(pq_acutal, p_f, q_f):
            assert xy == x*y

    results = await run_test_program(_prog, test_runner, n, t)
    assert len(results) == n


@mark.asyncio
async def test_cant_multiply_shares_from_different_contexts(test_preprocessing):
    from honeybadgermpc.mpc import TaskProgramRunner
    import asyncio

    n, t = 9, 2

    [test_preprocessing.generate(i, n, t, k=2000) for i in ['double_shares', 'rands']]

    async def _prog(context):
        share = context.Share(1)
        return share

    test_runner_1 = TaskProgramRunner(n, t)
    test_runner_2 = TaskProgramRunner(n, t)

    test_runner_1.add(_prog)
    test_runner_2.add(_prog)

    s1, s2 = await asyncio.gather(test_runner_1.join(), test_runner_2.join())

    async def _prog2(context):
        with raises(TypeError):
            await s1[0] * s2[0]

    test_runner_3 = TaskProgramRunner(
        n, t, {DoubleSharingMultiply.name, DoubleSharingMultiply()})
    test_runner_3.add(_prog2)
    await test_runner_3.join()


@mark.asyncio
async def test_beaver_mul_with_zeros(test_preprocessing, test_runner):
    x_secret, y_secret = 10, 15

    async def _prog(context):
        # Example of Beaver multiplication
        x = test_preprocessing.elements.get_zero(context) + context.Share(x_secret)
        y = test_preprocessing.elements.get_zero(context) + context.Share(y_secret)

        xy = await (x*y)

        x_, y_, xy_ = await gather(x.open(), y.open(), xy.open())
        assert x_ * y_ == xy_

        print("[%d] Finished" % (context.myid,), x_, y_, xy_)
        return xy_

    results = await run_test_program(_prog, test_runner)
    assert len(results) == n
    assert all(res == x_secret * y_secret for res in results)


@mark.asyncio
async def test_beaver_mul(test_preprocessing, test_runner):
    async def _prog(context):
        # Example of Beaver multiplication
        x = test_preprocessing.elements.get_rand(context)
        y = test_preprocessing.elements.get_rand(context)

        xy = await (x*y)

        x_, y_, xy_ = await gather(x.open(), y.open(), xy.open())
        assert x_ * y_ == xy_

        print("[%d] Finished" % (context.myid,), x_, y_, xy_)
        return xy_

    results = await run_test_program(_prog, test_runner)
    assert len(results) == n


@mark.asyncio
async def test_batch_beaver_multiply(test_preprocessing, test_runner):
    async def _prog(context):
        shares = [test_preprocessing.elements.get_rand(context) for _ in range(20)]
        p = context.ShareArray(shares[:10])
        q = context.ShareArray(shares[10:])

        p_f, q_f = await gather(p.open(), q.open())
        pq_actual = await (await (p*q)).open()
        for xy, x, y in zip(pq_actual, p_f, q_f):
            assert xy == x*y

    results = await run_test_program(_prog, test_runner)
    assert len(results) == n


@mark.asyncio
async def test_equality(test_preprocessing, galois_field, test_runner):
    equality = Equality()

    async def _prog(context):
        share0 = test_preprocessing.elements.get_zero(context)
        share1 = test_preprocessing.elements.get_rand(context)
        share1_ = share0 + share1
        share2 = test_preprocessing.elements.get_rand(context)

        assert await (await equality(context, share1, share1_)).open()
        assert await (share1 == share1_).open()
        assert not await (share1 == share2).open()

    results = await run_test_program(_prog, test_runner)
    assert len(results) == n


@mark.asyncio
async def test_invert_share(test_preprocessing, test_runner):
    inverter = InvertShare()

    async def _prog(context):
        share = test_preprocessing.elements.get_rand(context)
        # assert 1/x * x == 1
        inverted = await inverter(context, share)
        assert await (inverted * share).open() == 1

    results = await run_test_program(_prog, test_runner)
    assert len(results) == n


@mark.asyncio
async def test_invert_share_array(test_preprocessing, test_runner):
    inverter = InvertShareArray()

    async def _prog(context):
        shares = context.ShareArray(
            [test_preprocessing.elements.get_rand(context) for _ in range(20)])
        inverted_shares = await(inverter(context, shares))

        product = await(shares * inverted_shares)
        for e in await(product).open():
            assert e == 1

    results = await run_test_program(_prog, test_runner)
    assert len(results) == n


@mark.asyncio
async def test_share_division(test_preprocessing, test_runner):
    async def _prog(context):
        r1 = test_preprocessing.elements.get_rand(context)
        assert await(await(r1 / r1)).open() == 1

    results = await run_test_program(_prog, test_runner)
    assert len(results) == n


@mark.asyncio
async def test_share_division_needs_mixins(test_preprocessing, test_runner):
    async def _prog(context):
        r1 = test_preprocessing.elements.get_rand(context)
        with raises(NotImplementedError):
            assert await(await(r1 / r1)).open() == 1

    results = await run_test_program(_prog, test_runner, mixins=[])
    assert len(results) == n


@mark.asyncio
async def test_share_array_division(test_preprocessing, test_runner):
    n, t = 3, 1
    test_preprocessing.generate("triples", n, t)
    test_preprocessing.generate("rands", n, t)

    async def _prog(context):
        shares = context.ShareArray(
            [test_preprocessing.elements.get_rand(context) for _ in range(20)])

        result = await(shares / shares)
        for e in await(result).open():
            assert e == 1

    results = await run_test_program(_prog, test_runner)
    assert len(results) == n