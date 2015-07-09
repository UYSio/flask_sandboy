"""Base service for all RESTful endpoints."""
from flask import request, make_response
from flask.views import MethodView

from flask_sandboy.models import verify_fields
from flask_sandboy.exception import NotFoundException


class ReadService(MethodView):
    """Base class for all resources."""

    __model__ = None
    __db__ = None

    def _render(self, tup):
        if self.renderer:
            return self.renderer(tup)
        else:
            return tup

    def get(self, resource_id):
        """Return response to HTTP GET request."""
        if resource_id is None:
            return self._all_resources()
        else:
            if ',' in resource_id:
                return self._all_resources(ids=resource_id.split(','))
            else:
                resource = self._resource(resource_id)
                if not resource:
                    raise NotFoundException
                return self._render((resource.to_dict(), 200, {}))

    def _all_resources(self, ids=None):
        """Return all resources of this type as a JSON list."""
        builder = self.__model__.query
        for key in request.args:
            if hasattr(self.__model__, key):
                vals = request.args.getlist(key)
                builder = builder.filter(getattr(self.__model__, key).in_(vals))
        if ids:
            builder = builder.filter(self.__model__.id.in_(ids))
        if not 'page' in request.args:
            resources = builder.all()
        else:
            resources = builder.paginate(
                int(request.args['page'])).items
        dct = {'resources': [resource.to_dict() for resource in resources]}
        return self._render((dct, 200, {}))


    def _resource(self, resource_id):
        """Return resource represented by this *resource_id*."""
        resource = self.__db__.session.query(self.__model__).get(resource_id)
        if not resource:
            return None
        return resource


class WriteService(ReadService):

    @verify_fields
    def post(self, resource_id=None):
        """Return response to HTTP POST request."""
        # pylint: disable=unused-argument
        resource = self.__model__.query.filter_by(**request.json).first()
        # resource already exists; don't create it again
        if resource:
            return self._no_content_response()
        instance = self.__model__(  # pylint: disable=not-callable
            **request.json)
        self.__db__.session.add(instance)
        self.__db__.session.commit()
        return self._created_response(instance.to_dict())

    def delete(self, resource_id):
        """Return response to HTTP DELETE request."""
        instance = self._resource(resource_id)
        self.__db__.session.delete(instance)
        self.__db__.session.commit()
        return self._no_content_response()

    @verify_fields
    def put(self, resource_id):
        """Return response to HTTP PUT request."""
        instance = self._resource(resource_id)
        if instance is None:
            instance = self.__model__(   # pylint: disable=not-callable
                **request.json)
        else:
            instance.from_dict(request.json)
        self.__db__.session.add(instance)
        self.__db__.session.commit()
        return self._created_response(instance.to_dict())

    @verify_fields
    def patch(self, resource_id):
        """Return response to HTTP PATCH request."""
        resource = self._resource(resource_id)
        resource.from_dict(request.json)
        self.__db__.session.add(resource)
        self.__db__.session.commit()
        return self._created_response(resource.to_dict())

    def _no_content_response(self):
        """Return an HTTP 204 "No Content" response."""
        return self._render(({}, 204, {}))

    def _created_response(self, resource):
        """Return an HTTP 201 "Created" response."""
        return self._render((resource, 201, {}))
