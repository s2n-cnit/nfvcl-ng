


class pnfAPI(Resource):
    # Fixme add validation decorator
    @validate_json
    def post(self):
        msg = request.get_json()
        thread = Thread(target=pnf_manager.create, args=(msg,))
        thread.daemon = True
        thread.start()
        data = {'operation': 'create', 'status': 'submitted', 'resource': 'pnf'}
        return app.response_class(response=json.dumps(data), status=202, mimetype='application/json')

    @staticmethod
    def get():
        data = pnf_manager.get()
        if data is None:
            data = []

        return app.response_class(response=json.dumps(data), status=202, mimetype='application/json')