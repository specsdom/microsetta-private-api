from Crypto.Cipher import AES
from Crypto import Random
from base64 import b64decode, b64encode
from werkzeug.exceptions import BadRequest
from werkzeug.urls import url_encode

from microsetta_private_api.config_manager import AMGUT_CONFIG
from microsetta_private_api.LEGACY.locale_data import american_gut, british_gut


def gen_survey_url(survey_id, language_tag):
    # TODO: Is this the right way to do localization here?
    if language_tag == "en_us":
        text_locale = american_gut.text_locale
    elif language_tag == "en_gb":
        text_locale = british_gut.text_locale
    else:
        raise BadRequest("Unknown Locale: " + language_tag)

    """Return a formatted text block and URL for the external survey"""
    # TODO: Putting this text around the url is super weird, is this part up
    #  to departure to implement correctly and all we need is the url?
    tl = text_locale['human_survey_completed.html']
    embedded_text = tl['SURVEY_VIOSCREEN']
    regcode = AMGUT_CONFIG.vioscreen_regcode
    # TODO: If we have problems getting the ciphertext to be accepted by
    #  vioscreen, it could be due to switching to use of werkzeugs url_encode
    #  rather than tornado's url_escape.  But that has to wait until I can
    #  test with the actual key and registration code.
    url = "https://vioscreen.com/remotelogin.aspx?%s" % \
          url_encode(
              {
                  "Key": encrypt_key(survey_id, language_tag),
                  "RegCode": regcode
              }
          )
    return embedded_text % url


def pkcs7_pad_message(in_message):
    # http://stackoverflow.com/questions/14179784/python-encrypting-with-pycrypto-aes
    length = 16 - (len(in_message) % 16)
    return in_message + chr(length) * length


def pkcs7_unpad_message(in_message, ):
    return in_message[:-ord(in_message[-1])]


def encrypt_key(survey_id, language_tag):
    # TODO: Is this the right way to do localization here?
    if language_tag == "en_us":
        media_locale = american_gut.media_locale
    elif language_tag == "en_gb":
        media_locale = british_gut.media_locale
    else:
        raise BadRequest("Unknown Locale: " + language_tag)

    """Encode minimal required vioscreen information to AES key"""
    firstname = "NOT"
    lastname = "IDENTIFIED"
    gender_id = 2
    dob = '01011800'

    regcode = AMGUT_CONFIG.vioscreen_regcode

    # TODO: Specifying a callback url that goes back to our api server is, once
    #  again, super weird.  How is this supposed to work with callbacks?

    # TODO: What is supposed to go here for return url!?
    #  Theoretically it should be some departure website callback, which means
    #  they need to specify that to our api?  (AND register it with vioscreen?)
    returnurl = "http://microbio.me%s%s" % (media_locale["SITEBASE"],
                                            "/authed/vspassthrough/")
    assess_query = ("FirstName=%s&LastName=%s"
                    "&RegCode=%s"
                    "&Username=%s"
                    "&DOB=%s"
                    "&Gender=%d"
                    "&AppId=1&Visit=1&EncryptQuery=True&ReturnUrl={%s}" %
                    (firstname, lastname, regcode, survey_id, dob, gender_id,
                     returnurl))

    # PKCS7 add bytes equal length of padding
    pkcs7_query = pkcs7_pad_message(assess_query)

    # Generate AES encrypted information string
    key = AMGUT_CONFIG.vioscreen_cryptokey
    iv = Random.new().read(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)

    encoded = b64encode(iv + cipher.encrypt(pkcs7_query))
    return encoded


def decode_key(encoded):
    """decode AES and remove IV and PKCS#7 padding"""
    key = AMGUT_CONFIG.vioscreen_cryptokey
    iv = Random.new().read(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return pkcs7_unpad_message(cipher.decrypt(b64decode(encoded))[16:])