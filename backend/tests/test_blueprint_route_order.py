import unittest

from main import create_app
from app.api.routes.blueprints import router as blueprint_router


class BlueprintRouteOrderTests(unittest.TestCase):
    def test_overview_route_is_declared_before_blueprint_id_route(self):
        create_app()
        paths = [route.path for route in blueprint_router.routes]
        overview = "/projects/{project_id}/blueprint/overview"
        blueprint_id = "/projects/{project_id}/blueprint/{blueprint_id}"

        self.assertLess(paths.index(overview), paths.index(blueprint_id))


if __name__ == "__main__":
    unittest.main()