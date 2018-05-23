from unittest import TestCase

import cothread.catools as ca
from datetime import datetime

from test.brick.testbrick import TestBrick, DECIMALS
from cothread import Sleep
from test.brick.movemonitor import MoveMonitor, MotorCallback


# These tests verify real and virtual motors interact correctly


class TestDirect(TestCase):

    def test_direct_deferred_moves_cs(self):
        """ verify coordinated deferred direct moves work in quick succession
            i16 diffractometer style
        """
        tb = TestBrick()
        tb.set_cs_group(tb.g3)
        waiter = MotorCallback()

        for iteration in range(1):
            for height in range(10, 0, -2):
                angle = height / 20.0
                # todo mixing direct and standard moves to check for race conditions FAILS
                tb.all_go_direct([tb.jack1, tb.jack2], [0, 0])
                self.assertAlmostEqual(tb.height.pos, 0, DECIMALS)
                self.assertAlmostEqual(tb.angle.pos, 0, DECIMALS)

                tb.cs3.set_deferred_moves(True)

                waiter.reset_done()
                tb.height.go_direct(height, callback=waiter.moves_done, wait=False)
                tb.angle.go_direct(angle, wait=False)
                Sleep(.2)

                # verify no motion yet
                self.assertAlmostEqual(tb.height.pos, 0, DECIMALS)
                self.assertAlmostEqual(tb.angle.pos, 0, DECIMALS)

                start = datetime.now()
                tb.cs3.set_deferred_moves(False)
                waiter.wait_for_done()
                elapsed = datetime.now() - start
                print("Iteration {}. Direct Deferred Coordinated to height {} took {}".format(iteration, height, elapsed))

                # verify motion
                self.assertAlmostEqual(tb.height.pos, height, DECIMALS)
                self.assertAlmostEqual(tb.angle.pos * 10, angle * 10, DECIMALS)

    def test_quick(self):
        # prove that timings work OK when not using the TesBrick class
        ca.caput('BRICK1:M5.VMAX', 10, wait=True, timeout=60)
        ca.caput('BRICK1:M5.VELO', 10, wait=True, timeout=60)
        ca.caput('BRICK1:M5', 0.1, wait=True, timeout=60)

        ca.caput('BRICK1:M5:DirectDemand', 10, wait=True, timeout=60)
        start = datetime.now()
        ca.caput('BRICK1:M5:DirectDemand', 0, wait=True, timeout=60)
        elapsed = datetime.now() - start
        print(elapsed)
        self.assertLess(elapsed.seconds, 1.5)

        start = datetime.now()
        ca.caput('BRICK1:M5:DirectDemand', 1, wait=True, timeout=60)
        elapsed = datetime.now() - start
        print(elapsed)
        self.assertLess(elapsed.seconds, 1.5)

    def test_real_moves_cs(self):
        """ check that virtual axes update as expected on real axis moves
        """
        tb = TestBrick()
        tb.set_cs_group(tb.g3)

        # tb.jack1.go_direct(5)
        # tb.jack2.go_direct(5)
        tb.all_go_direct([tb.jack1, tb.jack2], [5, 5])

        # check height(x) and angle(y) in CS3
        self.assertAlmostEqual(tb.height.pos, 5, DECIMALS)
        self.assertAlmostEqual(tb.angle.pos, 0, DECIMALS)

    def test_cs_moves_real(self):
        """ check that real axes update as expected on virtual axis moves
        """
        tb = TestBrick()
        tb.set_cs_group(tb.g3)

        tb.height.go_direct(5)

        self.assertAlmostEqual(tb.jack1.pos, 5, DECIMALS)
        self.assertAlmostEqual(tb.jack2.pos, 5, DECIMALS)

    def test_cs_demand_updates(self):
        """ checks that the internal Q7x demand is updated on a real axis move
        """
        tb = TestBrick()
        tb.set_cs_group(tb.g3)

        tb.jack1.go_direct(2)
        self.assertAlmostEqual(tb.height.pos, 1, DECIMALS)

        tb.angle.go_direct(0)
        # if the Q77 demand for height axis X was not updated then it would return to prev pos 0
        self.assertAlmostEqual(tb.height.pos, 1, DECIMALS)
        self.assertAlmostEqual(tb.jack1.pos, 1, DECIMALS)
        self.assertAlmostEqual(tb.jack2.pos, 1, DECIMALS)

    def test_velocity_real(self):
        """ verify the speed of direct real axes
        """

        tb = TestBrick()
        tb.set_cs_group(tb.g1)

        # direct demand axes will go at the speed of the most recent standard motor record
        # move. This is not ideal but direct axes are really intended for use with deferred moves
        tb.m5.set_speed(10)
        tb.m5.go(0.1)
        start = datetime.now()
        tb.m5.go_direct(10)
        elapsed = datetime.now() - start
        print(elapsed)
        self.assertAlmostEqual(tb.m5.pos, 10, DECIMALS)
        self.assertLess(elapsed.seconds, 2)

        tb.m5.go(0)
        tb.m5.set_speed(2)
        tb.m5.go(0.1)
        start = datetime.now()
        tb.m5.go_direct(10)
        elapsed = datetime.now() - start
        print(elapsed)
        self.assertAlmostEqual(tb.m5.pos, 10, DECIMALS)
        self.assertTrue(5 <= elapsed.seconds < 7)

    def test_velocity_cs(self):
        """ verify the speed of direct virtual axes
        """
        tb = TestBrick()
        tb.set_cs_group(tb.g3)

        tb.height.set_speed(2)
        tb.height.go(0.1)

        start = datetime.now()
        tb.height.go_direct(10)
        elapsed = datetime.now() - start
        print(elapsed)
        self.assertAlmostEqual(tb.height.pos, 10, DECIMALS)
        self.assertTrue(5 <= elapsed.seconds < 7)

        tb.height.set_speed(100)
        tb.height.go(0)
        # set max motion program speed of jack 1 (axis 3) to 2mm/s
        # cts/msec is the same as mm/s if mres = .001
        tb.send_command('i316=2')
        start = datetime.now()
        tb.height.go(10)
        elapsed = datetime.now() - start
        print(elapsed)
        self.assertAlmostEqual(tb.height.pos, 10, DECIMALS)
        # the faster velocity should be overridden by max program speed of jack 1
        self.assertTrue(5 <= elapsed.seconds < 7)

        # set max motion program speed of jack 1 (axis 3) to 500mm/s
        tb.send_command('i316=500')
        tb.height.go(0)
        start = datetime.now()
        tb.height.go(10)
        elapsed = datetime.now() - start
        print(elapsed)
        # this time the motor speed restriction does not apply and the motion is fast
        self.assertAlmostEqual(tb.height.pos, 10, DECIMALS)
        self.assertTrue(elapsed.seconds < 1.5)

    def test_direct_deferred_cs_move_timing(self):
        tb = TestBrick()
        tb.set_cs_group(tb.g3)
        waiter = MotorCallback()

        tb.cs3.set_deferred_moves(True)
        tb.height.go_direct(1, callback=waiter.moves_done, wait=False)

        start = datetime.now()
        tb.cs3.set_deferred_moves(False)
        waiter.wait_for_done()

        elapsed = datetime.now() - start
        print("move height 1mm took {}".format(elapsed))
        self.assertLess(elapsed.seconds, 1)

    def test_direct_deferred_moves(self):
        """ verify real motor deferred direct moves work in quick succession
            using virtual 1-1 mapped axes which also have a CS motor record
        """
        tb = TestBrick()
        tb.set_cs_group(tb.g1)
        waiter = MotorCallback()

        for iteration in range(1):
            for height1 in range(10, 1, -2):
                height2 = height1 / 2.0
                # todo mixing direct and standard moves to verify no race conditions FAILS
                # todo   the occasional failure is probably due to the two separate busy records
                # todo   interaction - I think this is noncritical since it is not a required
                # todo   use case
                # tb.all_go([tb.jack1, tb.jack2], [0, 0])
                tb.all_go_direct([tb.jack1, tb.jack2], [0, 0])
                # tb.all_go_direct([tb.jack1, tb.jack2], [0, 0])
                self.assertAlmostEqual(tb.jack1.pos, 0, DECIMALS)
                self.assertAlmostEqual(tb.jack2.pos, 0, DECIMALS)

                tb.set_deferred_moves(True)
                waiter.reset_done()

                tb.jack1.go_direct(height1, callback=waiter.moves_done, wait=False)
                tb.jack1.go_direct(height1, wait=False)
                tb.jack2.go_direct(height2, wait=False)
                Sleep(.2)

                # verify no motion yet
                self.assertAlmostEqual(tb.jack1.pos, 0, DECIMALS)
                self.assertAlmostEqual(tb.jack2.pos, 0, DECIMALS)

                start = datetime.now()
                tb.set_deferred_moves(False)
                Sleep(.1)
                waiter.wait_for_done()
                elapsed = datetime.now() - start
                print("Iteration {}. Direct Deferred real motors to height {} took {}".format(iteration, height1, elapsed))

                # verify motion
                self.assertAlmostEqual(tb.jack1.pos, height1, DECIMALS)
                self.assertAlmostEqual(tb.jack2.pos, height2, DECIMALS)

    def test_small_steps(self):
        """ verify real motor deferred direct moves work in quick succession
            using virtual 1-1 mapped axes with CS motor record

            (copied from i16 tests)
        """
        tb = TestBrick()
        tb.set_cs_group(tb.g1)
        waiter = MotorCallback()

        kphi = tb.kphi.pos
        kappa = tb.kappa.pos
        ktheta = tb.ktheta.pos
        for i in range(1, 5):
            # set up deferred move
            waiter.reset_done()
            tb.cs2.set_deferred_moves(True)

            next_kphi = kphi + 1
            next_kappa = kappa + .01
            next_ktheta = ktheta + .01

            print('deferred move to kphi {}, kappa {}, ktheta {}'.format(
                next_kphi, next_kappa, next_ktheta))

            tb.cs2.kphi.go_direct(next_kphi, callback=waiter.moves_done, wait=False)
            tb.cs2.kappa.go_direct(next_kappa, wait=False)
            tb.cs2.ktheta.go_direct(next_ktheta, wait=False)
            Sleep(.1)

            # verify no motion yet
            self.assertAlmostEquals(tb.kphi.pos, kphi, DECIMALS)
            self.assertAlmostEquals(tb.kappa.pos, kappa, DECIMALS)
            self.assertAlmostEquals(tb.ktheta.pos, ktheta, DECIMALS)

            # make the move
            tb.cs2.set_deferred_moves(False)
            waiter.wait_for_done()

            # verify motion
            self.assertAlmostEquals(tb.kphi.pos, next_kphi, DECIMALS)
            self.assertAlmostEquals(tb.kappa.pos, next_kappa, DECIMALS)
            self.assertAlmostEquals(tb.ktheta.pos, next_ktheta, DECIMALS)

            kphi = next_kphi
            kappa = next_kappa
            ktheta = next_ktheta