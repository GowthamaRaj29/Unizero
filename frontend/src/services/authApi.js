import api from "./api";

export const loginUser = async ({
  email,
  password,
}) => {
  return api("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      username: email,
      email,
      password,
    }),
  });
};

export const registerUser = async ({
  full_name,
  email,
  password,
  role,
}) => {
  return api("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      full_name,
      email,
      password,
      role,
    }),
  });
};

export const getCurrentUser = async () => {
  return api("/auth/me", {
    method: "GET",
  });
};