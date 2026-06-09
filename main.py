import libs.reachyController as ry

if __name__ == "__main__":
    reachy = ry.ReachyController.instanciate()

    test0 = ry.Instructor.loadFromPath('test.yml', reachy)
    test0.execute()