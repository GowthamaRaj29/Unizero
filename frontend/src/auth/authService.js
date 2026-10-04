import {
  loginUser,
  registerUser,
  getCurrentUser,
} from "../services/authApi";

export const login = async (email, password) => {
  const response = await loginUser({
    email,
    password,
  });

  const token =
    response?.access_token ||
    response?.token;

  const user = response?.user || {
    id: response?.user_id,
    username: response?.username,
    email: email,
    role: response?.role,
  };

  if (!token) {
    throw new Error(
      "Login succeeded but no access token was returned."
    );
  }

  localStorage.setItem(
    "access_token",
    token
  );

  if (user) {
    localStorage.setItem(
      "user",
      JSON.stringify(user)
    );
  }

  return {
    token,
    user,
  };
};

export const register = async ({
  full_name,
  email,
  password,
  role,
}) => {
  return registerUser({
    full_name,
    email,
    password,
    role,
  });
};

export const fetchCurrentUser = async () => {
  const user = await getCurrentUser();

  localStorage.setItem(
    "user",
    JSON.stringify(user)
  );

  return user;
};

export const logout = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("user");
};

export const getStoredUser = () => {
  const storedUser =
    localStorage.getItem("user");

  if (!storedUser) {
    return null;
  }

  try {
    return JSON.parse(storedUser);
  } catch {
    return null;
  }
};

export const getToken = () => {
  return localStorage.getItem(
    "access_token"
  );
};

export const isAuthenticated = () => {
  return Boolean(getToken());
};