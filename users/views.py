import os
import requests
from django.contrib import messages
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth import authenticate, login, logout
from django.contrib.messages.views import SuccessMessageMixin
from django.core.files.base import ContentFile
from django.shortcuts import redirect, reverse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, DetailView, UpdateView, RedirectView

from core import mixins
from . import forms, models


class LoginView(mixins.LoggedOutOnlyMixin, SuccessMessageMixin, FormView):

    """ Log in View """

    template_name = "users/login.html"
    form_class = forms.LoginForm
    success_message = "로그인 되었습니다!"

    def form_valid(self, form):
        email = form.cleaned_data.get("email")
        password = form.cleaned_data.get("password")
        user = authenticate(self.request, username=email, password=password)

        if user is not None:
            login(self.request, user)

        return super().form_valid(form)

    def get_success_url(self):
        next_arg = self.request.GET.get("next")
        if next_arg is not None:
            return next_arg
        else:
            return reverse("core:home")


class LogoutView(
    mixins.LoggedInOnlyMixin, mixins.NotFormSuceesMessageMixin, RedirectView
):

    """ Log out View """

    url = reverse_lazy("core:home")
    success_message = "로그아웃 되었습니다."

    def get(self, request, *args, **kwargs):
        logout(request)
        return super(LogoutView, self).get(request, *args, **kwargs)


class SignOutView(mixins.NotFormSuceesMessageMixin, RedirectView):

    """ Sign out View """

    url = reverse_lazy("core:home")
    success_message = "탈퇴되었습니다! 다시 만날 수 있었으면 좋겠네요!"

    def get(self, request, *args, **kwargs):
        try:
            login_method = request.user.login_method
            if login_method == models.User.LOGIN_KAKAO:
                return redirect(reverse("users:kakao-leave"), request)
            else:
                request.user.delete()
        except models.User.Exception:
            messages.error(f"탈퇴에 실패했습니다!")
        return super(SignOutView, self).get(request, *args, **kwargs)


class SignUpView(mixins.LoggedOutOnlyMixin, FormView):

    """ Sign Up View """

    template_name = "users/signup.html"
    form_class = forms.SignUpForm
    success_url = reverse_lazy("core:home")

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(SignUpView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        email = form.cleaned_data.get("email")
        password = form.cleaned_data.get("password")
        user = authenticate(self.request, username=email, password=password)

        if user is not None:
            login(self.request, user)
        user.verify_email()
        return super().form_valid(form)


class CompleteVerificationView(mixins.NotFormSuceesMessageMixin, RedirectView):

    """ Verification Complete View """

    url = reverse_lazy("core:home")
    success_message = "인증이 완료되었습니다."

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(CompleteVerificationView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        try:
            user = models.User.objects.get(email_secret=self.kwargs["key"])
            user.email_verified = True
            user.email_secret = ""
            user.save()

        except models.User.DoesNotExist:
            messages.error(self.request, "사용자가 존재하지 않습니다.")
        return super(CompleteVerificationView, self).get(request, *args, **kwargs)


# 1. Request a user's Github identity
def github_login(request):
    client_id = os.environ.get("GH_ID")
    domain = os.environ.get("DOMAIN")
    redirect_uri = f"{domain}/users/login/github/callback"
    return redirect(
        f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope=read:user"
    )


class GithubException(Exception):
    pass


# 2. USers are redirected back to your site by Github
def github_callback(request):
    try:
        client_id = os.environ.get("GH_ID")
        client_secret = os.environ.get("GH_SECRET")
        code = request.GET.get("code", None)
        # Exchange the 'code' for an access token
        if code is not None:
            # Receive the content's formats depending on the Accpept header
            token_request = requests.post(
                f"https://github.com/login/oauth/access_token?client_id={client_id}&client_secret={client_secret}&code={code}",
                headers={"Accept": "application/json"},
            )
            # 3. User access token to access the API
            token_json = token_request.json()
            error = token_json.get("error", None)
            if error is not None:
                raise GithubException("Can't get access token")
            else:
                access_token = token_json.get("access_token")
                profile_request = requests.get(
                    f"https://api.github.com/user",
                    headers={
                        "Authorization": f"token {access_token}",
                        "Accept": "application/json",
                    },
                )
                profile_json = profile_request.json()
                username = profile_json.get("email", None)
                # Github login using OAuth
                if username is not None:
                    name = profile_json.get("name")
                    email = profile_json.get("email")
                    bio = profile_json.get("bio")
                    try:
                        user = models.User.objects.get(email=email)
                        if user.login_method != models.User.LOGIN_GITHUB:
                            raise GithubException(
                                f"Please log in with: {user.login_method}"
                            )
                    except models.User.DoesNotExist:
                        user = models.User.objects.create(
                            email=email,
                            first_name=name,
                            username=email,
                            bio=bio,
                            login_method=models.User.LOGIN_GITHUB,
                            email_verified=True,
                        )
                        user.set_unusable_password()
                        user.save()
                    login(request, user)
                    messages.success(request, f"Welcome back {user.first_name}")
                    return redirect(reverse("core:home"))
                else:
                    raise GithubException("Can't get your profile")
        else:
            raise GithubException("Can't get code")
    except GithubException as e:
        messages.error(request, e)
        return redirect(reverse("users:login"))


def kakao_leave(request):
    """ kakao 회원 탈퇴 """
    client_id = os.environ.get("KAKAO_ID")
    domain = os.environ.get("DOMAIN")
    redirect_uri = f"{domain}/users/leave/kakao/callback"
    return redirect(
        f"https://kauth.kakao.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"
    )


def kakao_leave_callback(request):
    try:
        code = request.GET.get("code", None)
        client_id = os.environ.get("KAKAO_ID")
        domain = os.environ.get("DOMAIN")
        redirect_uri = f"{domain}/users/leave/kakao/callback"
        token_request = requests.get(
            f"https://kauth.kakao.com/oauth/token?grant_type=authorization_code&client_id={client_id}&redirect_uri={redirect_uri}&code={code}"
        )
        token_json = token_request.json()
        error = token_json.get("error", None)

        if error is not None:
            raise KakaoException("Can't get authorization code.")
        access_token = token_json.get("access_token")
        profile_request = requests.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-type": "application/x-www-form-urlencoded;charset=utf-8",
            },
        )
        profile_json = profile_request.json().get("kakao_account")
        email = profile_json.get("email", None)

        leave_request = requests.post(
            f"https://kapi.kakao.com//v1/user/unlink",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        leave_id = leave_request.json().get("id", None)

        if leave_id is not None:
            user = models.User.objects.get(email=email)
            user.delete()
            messages.info(request, f"Good bye!")
            return redirect(reverse("core:home"))

    except KakaoException as e:
        messages.error(request, e)
        return redirect(reverse("core:home"))


def kakao_login(request):
    client_id = os.environ.get("KAKAO_ID")
    domain = os.environ.get("DOMAIN")
    redirect_uri = f"{domain}/users/login/kakao/callback"
    return redirect(
        f"https://kauth.kakao.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"
    )


class KakaoException(Exception):
    pass


def kakao_login_callback(request):
    try:
        code = request.GET.get("code", None)
        client_id = os.environ.get("KAKAO_ID")
        domain = os.environ.get("DOMAIN")
        redirect_uri = f"{domain}/users/login/kakao/callback"
        token_request = requests.get(
            f"https://kauth.kakao.com/oauth/token?grant_type=authorization_code&client_id={client_id}&redirect_uri={redirect_uri}&code={code}"
        )
        token_json = token_request.json()
        error = token_json.get("error", None)

        if error is not None:
            raise KakaoException("Can't get authorization code.")
        access_token = token_json.get("access_token")
        profile_request = requests.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-type": "application/x-www-form-urlencoded;charset=utf-8",
            },
        )

        profile_json = profile_request.json().get("kakao_account")
        email = profile_json.get("email", None)
        if email is None:
            raise KakaoException("Please also give me your email")
        properties = profile_request.json().get("properties")
        nickname = properties.get("nickname")
        profile_image = properties.get("profile_image", None)
        try:
            user = models.User.objects.get(email=email)
            if user.login_method != models.User.LOGIN_KAKAO:
                raise KakaoException(f"Please log in with: {user.login_method}")
        except models.User.DoesNotExist:
            user = models.User.objects.create(
                email=email,
                first_name=nickname,
                username=email,
                email_verified=True,
                login_method=models.User.LOGIN_KAKAO,
            )
            user.set_unusable_password()
            user.save()
            if profile_image is not None:
                photo_request = requests.get(profile_image)
                user.avatar.save(
                    f"{nickname}-avatar", ContentFile(photo_request.content())
                )
        messages.success(request, f"Welcome back {user.first_name}")
        login(request, user)
        return redirect(reverse("core:home"))
    except KakaoException as e:
        messages.error(request, e)
        return redirect(reverse("users:login"))


class UserProfileView(DetailView):

    """ User Profile View """

    model = models.User
    context_object_name = "user_obj"


class UpdateProfileView(SuccessMessageMixin, UpdateView):

    """ Update Profile View """

    model = models.User
    template_name = "users/profile-update.html"

    fields = [
        "first_name",
        "last_name",
        "avatar",
        "gender",
        "bio",
        "birthdate",
        "businessman",
    ]
    success_message = "사용자 정보가 변경되었습니다."

    context_object_name = "user_obj"

    def get_object(self, queryset=None):
        return self.request.user

    def get_form(self, form_class=None):
        form = super().get_form(form_class=form_class)
        form.fields["birthdate"].widget.attrs = {"placeholder": "Birthdate"}
        form.fields["first_name"].widget.attrs = {"placeholder": "First name"}
        form.fields["last_name"].widget.attrs = {"placeholder": "Last name"}
        form.fields["bio"].widget.attrs = {"placeholder": "Bio"}
        return form


class UpdatePasswordView(
    mixins.EmailLoginOnlyMixin,
    mixins.LoggedInOnlyMixin,
    SuccessMessageMixin,
    PasswordChangeView,
):

    """ Update Password View """

    template_name = "users/password-update.html"
    success_message = "비밀번호가 변경되었습니다."

    def get_form(self, form_class=None):
        form = super().get_form(form_class=form_class)
        form.fields["old_password"].widget.attrs = {"placeholder": "Current password"}
        form.fields["new_password"].widget.attrs = {
            "placeholder": "Cofirm new password"
        }
        return form
