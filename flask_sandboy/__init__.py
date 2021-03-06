"""Flask application that creates a RESTful API from SQLAlchemy models."""

from flask import (Blueprint, jsonify, current_app, )
import uuid

from flask_sandboy.service import WriteService, ReadService
from flask_sandboy.models import SerializableModel
from flask_sandboy.exception import (
    BadRequestException, ForbiddenException, NotAcceptableException,
    NotFoundException, ConflictException, ServerErrorException,
    NotImplementedException, ServiceUnavailableException)

__version__ = '0.0.4'


def default_render(service_response):
    """
    The default render function for responses returned by
    the service.

    Accepts a tuple of the form:
    (dict, status_code, headers)
    and turns it into a Flask JSON response.
    """
    response, status, headers = service_response
    flask_response = jsonify(response)
    flask_response.status_code = status
    for key in headers:
        flask_response.headers.add(key, headers[key])
    return flask_response


class Sandboy(object):
    """Main object for injecting RESTful HTTP endpoint."""

    def __init__(self, app, db, models,
                 url_prefix=None,
                 readonly=False,
                 before_request=[],
                 decorators=[],
                 renderer=default_render):
        """Initialize and register the given *models*."""
        self.app = app
        self.db = db
        app.extensions['sandboy'] = self
        self.blueprint = None
        self.url_prefix = url_prefix
        self.readonly = readonly
        self.before_request = before_request
        self.decorators = decorators
        self.renderer = renderer
        self.init_app(app, models)

    def _log_and_get_token(self, error):
        error_token = str(uuid.uuid4())
        current_app.logger.error('error_token=%s' % error_token)
        current_app.logger.exception(error)
        return error_token

    def init_app(self, app, models):
        """Initialize and register error handlers."""

        # pylint: disable=unused-variable
        self.blueprint = Blueprint('sandboy', __name__,
                                   url_prefix=self.url_prefix)
        for br in self.before_request:
            self.blueprint.before_request(br)

        @self.blueprint.errorhandler(BadRequestException)
        @self.blueprint.errorhandler(ForbiddenException)
        @self.blueprint.errorhandler(NotAcceptableException)
        @self.blueprint.errorhandler(NotFoundException)
        @self.blueprint.errorhandler(ConflictException)
        @self.blueprint.errorhandler(ServerErrorException)
        @self.blueprint.errorhandler(NotImplementedException)
        @self.blueprint.errorhandler(ServiceUnavailableException)
        @self.blueprint.errorhandler(Exception)
        def handle_application_error(error):
            """Handler used to send JSON error messages rather than default
            HTML ones."""
            if hasattr(error, 'to_dict'):
                error_dict = error.to_dict()
            else:
                # if it's an non-specific error
                error_dict = {'msg': 'An error occurred.'}
                error_token = self._log_and_get_token(error)
                error_dict.update({'error_token': error_token})

            response = jsonify(error_dict)

            if hasattr(error, 'code'):
                response.status_code = error.code
            else:
                response.status_code = 500
            return response

        self.register(models)
        app.register_blueprint(self.blueprint)

    def register(self, cls_list):
        """Register a class to be given a REST API."""
        for cls in cls_list:
            serializable_model = type(
                cls.__name__ + 'Serializable', (cls, SerializableModel), {})

            service = ReadService if self.readonly else WriteService

            service.decorators = self.decorators
            if self.renderer:
                service.renderer = lambda a,b: self.renderer(b)
            else:
                service.renderer = None

            new_endpoint = type(
                cls.__name__ + 'Endpoint', (service, ),
                {'__model__': serializable_model,
                 '__db__': self.db})
            view_func = new_endpoint.as_view(
                new_endpoint.__model__.__tablename__)
            self.blueprint.add_url_rule(
                '/' + new_endpoint.__model__.__tablename__,
                defaults={'resource_id': None},
                view_func=view_func)
            self.blueprint.add_url_rule(
                '/{resource}/<resource_id>'.format(
                    resource=new_endpoint.__model__.__tablename__),
                view_func=view_func)
