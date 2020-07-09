import flask
from flask import jsonify
from werkzeug.exceptions import BadRequest

from microsetta_private_api.api._account import _validate_account_access
from microsetta_private_api.model.sample import SampleInfo
from microsetta_private_api.model.source import Source
from microsetta_private_api.repo.kit_repo import KitRepo
from microsetta_private_api.repo.sample_repo import SampleRepo
from microsetta_private_api.repo.source_repo import SourceRepo
from microsetta_private_api.repo.survey_answers_repo import SurveyAnswersRepo
from microsetta_private_api.repo.transaction import Transaction
from microsetta_private_api.util.util import fromisotime


def read_sample_associations(account_id, source_id, token_info):
    _validate_account_access(token_info, account_id)

    with Transaction() as t:
        sample_repo = SampleRepo(t)
        samples = sample_repo.get_samples_by_source(account_id, source_id)

    api_samples = [x.to_api() for x in samples]
    return jsonify(api_samples), 200


def associate_sample(account_id, source_id, body, token_info):
    _validate_account_access(token_info, account_id)

    with Transaction() as t:
        sample_repo = SampleRepo(t)
        sample_repo.associate_sample(account_id,
                                     source_id,
                                     body['sample_id'])
        t.commit()
    response = flask.Response()
    response.status_code = 201
    response.headers['Location'] = '/api/accounts/%s/sources/%s/samples/%s' % \
                                   (account_id, source_id, body['sample_id'])
    return response


def read_sample_association(account_id, source_id, sample_id, token_info):
    _validate_account_access(token_info, account_id)

    with Transaction() as t:
        sample_repo = SampleRepo(t)
        sample = sample_repo.get_sample(account_id, source_id, sample_id)
        if sample is None:
            return jsonify(code=404, message="Sample not found"), 404

        return jsonify(sample.to_api()), 200


def update_sample_association(account_id, source_id, sample_id, body,
                              token_info):
    _validate_account_access(token_info, account_id)

    # TODO: API layer doesn't understand that BadRequest can be thrown,
    #  but that looks to be the right result if sample_site bad.
    #  Need to update the api layer if we want to specify 400s.
    #  (Or we leave api as is and say 400's can always be thrown if your
    #  request is bad)
    with Transaction() as t:
        sample_repo = SampleRepo(t)
        source_repo = SourceRepo(t)

        source = source_repo.get_source(account_id, source_id)
        if source is None:
            return jsonify(code=404, message="No such source"), 404

        needs_sample_site = source.source_type in [Source.SOURCE_TYPE_HUMAN,
                                                   Source.SOURCE_TYPE_ANIMAL]

        precludes_sample_site = source.source_type == \
            Source.SOURCE_TYPE_ENVIRONMENT

        sample_site_present = "sample_site" in body and \
                              body["sample_site"] is not None

        if needs_sample_site and not sample_site_present:
            # Human/Animal sources require sample_site to be set
            raise BadRequest("human/animal samples require sample_site")
        if precludes_sample_site and sample_site_present:
            raise BadRequest("environmental samples cannot specify "
                             "sample_site")

        sample_datetime = body['sample_datetime']
        try:
            sample_datetime = fromisotime(sample_datetime)
        except ValueError:
            raise BadRequest("Invalid sample_datetime")

        # sample_site will not be present if its environmental. this will
        # default to None if the key is not present
        sample_site = body.get('sample_site')
        sample_info = SampleInfo(
            sample_id,
            sample_datetime,
            sample_site,
            body["sample_notes"]
        )

        sample_repo.update_info(account_id, source_id, sample_info)
        final_sample = sample_repo.get_sample(account_id, source_id, sample_id)
        t.commit()
    return jsonify(final_sample), 200


def dissociate_sample(account_id, source_id, sample_id, token_info):
    _validate_account_access(token_info, account_id)

    with Transaction() as t:
        answers_repo = SurveyAnswersRepo(t)
        answered_survey_ids = answers_repo.list_answered_surveys_by_sample(
            account_id, source_id, sample_id)

        for curr_answered_survey_id in answered_survey_ids:
            answers_repo.dissociate_answered_survey_from_sample(
                account_id, source_id, sample_id, curr_answered_survey_id)

        sample_repo = SampleRepo(t)
        sample_repo.dissociate_sample(account_id, source_id, sample_id)

        t.commit()

        return '', 204


def associate_answered_survey(account_id, source_id, sample_id, body,
                              token_info):
    _validate_account_access(token_info, account_id)

    with Transaction() as t:
        answers_repo = SurveyAnswersRepo(t)
        answers_repo.associate_answered_survey_with_sample(
            account_id, source_id, sample_id, body['survey_id']
        )
        t.commit()

    response = flask.Response()
    response.status_code = 201
    response.headers['Location'] = '/api/accounts/%s' \
                                   '/sources/%s' \
                                   '/surveys/%s' % \
                                   (account_id,
                                    source_id,
                                    body['survey_id'])
    return response


def dissociate_answered_survey(account_id, source_id, sample_id, survey_id,
                               token_info):
    _validate_account_access(token_info, account_id)

    with Transaction() as t:
        answers_repo = SurveyAnswersRepo(t)
        answers_repo.dissociate_answered_survey_from_sample(
            account_id, source_id, sample_id, survey_id)
        t.commit()
    return '', 204


def read_kit(kit_name):
    # NOTE:  Nothing in this route requires a particular user to be logged in,
    # so long as the user has -an- account.

    with Transaction() as t:
        kit_repo = KitRepo(t)
        kit = kit_repo.get_kit_unused_samples(kit_name)
        if kit is None:
            return jsonify(code=404, message="No such kit"), 404
        return jsonify(kit.to_api()), 200
